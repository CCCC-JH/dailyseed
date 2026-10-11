package com.dailyseed.reminder;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 日历提醒的纯函数测试——不连数据库。
 *
 * <p>这里守的是两件容易悄悄坏掉的事：
 * ① 日历文件是<b>给别的软件解析的</b>，语法一错就是"文件无法导入"，本地完全看不出来；
 * ② 提醒必须<b>永不结束、按用户时区</b>——那是 §8.1「他自己设的提醒」的全部意思。
 */
class ReminderServiceTest {

    private static final LocalDate TODAY = LocalDate.parse("2026-10-09");

    private static String ics(LocalTime at) {
        return ReminderService.ics("每日一粒", "Asia/Shanghai", at, TODAY);
    }

    /** 折行后每一行的 UTF-8 字节数都必须 ≤ 75，且复原后与原文一字不差（多字节字符没被切断） */
    private static void assertFoldedIntact(String folded, String original) {
        for (String line : folded.split("\r\n")) {
            assertThat(line.getBytes(StandardCharsets.UTF_8).length)
                    .as("行超过 75 字节：%s", line)
                    .isLessThanOrEqualTo(75);
        }
        assertThat(folded.replace("\r\n ", "").replace("\r\n", "")).isEqualTo(original);
    }

    @Test
    @DisplayName("★ 按用户时区的当地 8 点响，而且每天一次、永不结束（§8.1：他自己设的提醒）")
    void isDailyAndTimezoneAware() {
        String ics = ics(LocalTime.of(8, 0));

        assertThat(ics).contains("DTSTART;TZID=Asia/Shanghai:20261009T080000");
        assertThat(ics).contains("DTEND;TZID=Asia/Shanghai:20261009T080500");
        assertThat(ics).contains("RRULE:FREQ=DAILY");
        // 不给提醒设终点：想停就自己在日历里删，我们不该替他决定"提醒 21 天就够了"
        assertThat(ics).doesNotContain("UNTIL");
        assertThat(ics).doesNotContain("COUNT=");
    }

    @Test
    @DisplayName("换个时区就是当地的同一个钟点（提醒跟着人走，不跟着服务器走）")
    void followsTheUsersTimezone() {
        String ics = ReminderService.ics("每日一粒", "Europe/Berlin", LocalTime.of(21, 0), TODAY);

        assertThat(ics).contains("DTSTART;TZID=Europe/Berlin:20261009T210000");
    }

    @Test
    @DisplayName("时区名写坏了不至于整份日历生成失败，退回默认时区")
    void brokenTimezoneFallsBack() {
        String ics = ReminderService.ics("每日一粒", "Mars/Olympus", LocalTime.of(8, 0), TODAY);

        assertThat(ics).contains("DTSTART;TZID=Asia/Shanghai:20261009T080000");
    }

    @Test
    @DisplayName("23:5x 的提醒会跨天：结束时间必须跟着到第二天，不能出现 END 早于 START")
    void lateReminderDoesNotProduceAnIllegalEvent() {
        String ics = ics(LocalTime.of(23, 58));

        assertThat(ics).contains("DTSTART;TZID=Asia/Shanghai:20261009T235800");
        assertThat(ics).contains("DTEND;TZID=Asia/Shanghai:20261010T000300");
    }

    @Test
    @DisplayName("没设过时间就用默认的 08:00（前端也用同一个默认值，两边不会各说各话）")
    void nullTimeUsesTheDefault() {
        assertThat(ics(null)).contains("DTSTART;TZID=Asia/Shanghai:20261009T080000");
        assertThat(ReminderService.DEFAULT_TIME).isEqualTo("08:00");
    }

    @Test
    @DisplayName("只收 HH:mm——宽松解析会让库里的格式五花八门")
    void onlyAcceptsStrictHHmm() {
        assertThat(ReminderService.parseTime("08:00")).contains(LocalTime.of(8, 0));
        assertThat(ReminderService.parseTime(" 21:30 ")).contains(LocalTime.of(21, 30));
        assertThat(ReminderService.parseTime("8:00")).isEmpty();
        assertThat(ReminderService.parseTime("08:00:00")).isEmpty();
        assertThat(ReminderService.parseTime("25:00")).isEmpty();
        assertThat(ReminderService.parseTime("08:61")).isEmpty();
        assertThat(ReminderService.parseTime(null)).isEmpty();
        assertThat(ReminderService.parseTime("晚上八点")).isEmpty();
    }

    @Test
    @DisplayName("★ 折行按 UTF-8 字节算，每行不超过 75 字节（按字符算会让中文行超到 200 多字节）")
    void foldsByBytesNotCharacters() {
        String ics = ics(LocalTime.of(8, 0));

        for (String line : ics.split("\r\n")) {
            assertThat(line.getBytes(StandardCharsets.UTF_8).length)
                    .as("行超过 75 字节：%s", line)
                    .isLessThanOrEqualTo(75);
        }
        // 中文摘要和描述一定会触发折行，续行必须以空格开头（RFC 5545）
        assertThat(ics).contains("\r\n ");
    }

    @Test
    @DisplayName("最终产出满足 RFC 5545 的硬性要求：CRLF 换行 + 首尾结构完整")
    void isAWellFormedCalendar() {
        String ics = ics(LocalTime.of(8, 0));

        assertThat(ics).startsWith("BEGIN:VCALENDAR\r\n");
        assertThat(ics).endsWith("END:VCALENDAR\r\n");
        assertThat(ics).contains("VERSION:2.0");
        assertThat(ics).contains("\r\nBEGIN:VEVENT\r\n");
        assertThat(ics).contains("\r\nEND:VEVENT\r\n");
        // 不能出现"裸 LF"（Unix 换行）——有些客户端会整份拒收
        assertThat(ics.replace("\r\n", "")).doesNotContain("\n");
        // 事件不该占住用户的时间（TRANSPARENT = 显示为"有空"）
        assertThat(ics).contains("TRANSP:TRANSPARENT");
    }

    @Test
    @DisplayName("转义 RFC 5545 要求的字符")
    void escapesSpecialCharacters() {
        assertThat(ReminderService.escape("a,b;c")).isEqualTo("a\\,b\\;c");
        assertThat(ReminderService.escape("换\n行")).isEqualTo("换\\n行");
        assertThat(ReminderService.escape("反\\斜杠")).isEqualTo("反\\\\斜杠");
    }

    @Test
    @DisplayName("★ 反斜杠必须最先替：库里若有一处 `\\,`，晚替会变成 `\\\\,`——导入后被读成转义符号本身")
    void backslashIsReplacedFirst() {
        assertThat(ReminderService.escape("\\,")).isEqualTo("\\\\\\,");
        // 换个顺序（先替逗号）就会得到 3 个字符而不是 4 个，这一条守着那个顺序
        assertThat(ReminderService.escape("\\,")).hasSize(4);
    }

    @Test
    @DisplayName("生成器不往里塞任何打卡/催促/号召语（红线 1、2）")
    void carriesNoNudging() {
        String ics = ics(LocalTime.of(8, 0));

        assertThat(ics).doesNotContain("别忘了");
        assertThat(ics).doesNotContain("打卡");
        assertThat(ics).doesNotContain("坚持");
        assertThat(ics).doesNotContain("http"); // 没有链接、没有二维码指向的东西
    }

    @Test
    @DisplayName("折行函数本身：短行原样、长行断在字节边界上且不切碎多字节字符")
    void foldKeepsMultiByteCharactersIntact() {
        assertThat(ReminderService.fold(List.of("短行"))).isEqualTo("短行\r\n");

        String long_ = "描述:".repeat(30);
        String folded = ReminderService.fold(List.of(long_));
        assertThat(folded).contains("\r\n ");
        assertFoldedIntact(folded, long_);
    }

    @Test
    @DisplayName("★ DTSTAMP 记的是「这份日历什么时候生成的」（UTC），不是提醒时刻——否则日历里会显示一个没发生过的创建时间")
    void dtstampIsTheRealGenerationTime() {
        String ics = ReminderService.ics("每日一粒", "Asia/Shanghai", LocalTime.of(21, 30), TODAY,
                java.time.Instant.parse("2026-10-09T13:30:00Z"));

        assertThat(ics).contains("DTSTAMP:20261009T133000Z");
        // 别把提醒时刻（21:30）当成创建时刻
        assertThat(ics).doesNotContain("DTSTAMP:20261009T213000");
    }

    @Test
    @DisplayName("UID 固定用日期，不掺随机数——同一份日历重复导入不该产生一堆重复日程")
    void uidIsStable() {
        assertThat(ics(LocalTime.of(8, 0))).isEqualTo(ics(LocalTime.of(8, 0)));
        assertThat(ics(LocalTime.of(8, 0))).contains("UID:dailyseed-20261009@dailyseed.local");
    }
}
