package com.dailyseed.reminder;

import com.dailyseed.user.UserStore;
import java.nio.charset.StandardCharsets;
import java.time.DateTimeException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 日历提醒（设计文档 §8.1）——**用户自己设的提醒，不是我们推送的**。
 *
 * <p>这是整个产品里唯一一个"召回"手段，而它刻意是零成本、零推送的：
 * 我们只是生成一个 .ics 文件，用户把它加进自己的日历，之后每天响的是<b>他自己的日历</b>。
 * 妙处不在技术上，在心理上——他设的这个动作本身就是一次承诺（§8.1）。
 *
 * <p>所以生成的日历事件里：没有打卡链接、没有"别忘了"、没有号召语，
 * 只有一句"今天那一粒"。响与不响都由他，随时删掉也行。
 */
@Service
public class ReminderService {

    /** 没设过就用这个。前端也用同一个默认值，两边不会各说各话 */
    public static final String DEFAULT_TIME = "08:00";

    /** 提醒是每天一次的"看一眼"，不是会议——5 分钟足够，也不占满日历格 */
    private static final int DURATION_MINUTES = 5;

    /** 对外也用同一套格式：接口收到什么就按什么回，前端不用再自己格式化一遍 */
    public static final DateTimeFormatter HHMM = DateTimeFormatter.ofPattern("HH:mm");

    private static final DateTimeFormatter ICS_DATE = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final DateTimeFormatter ICS_TIME = DateTimeFormatter.ofPattern("HHmmss");

    /** DTSTAMP 必须是 UTC（RFC 5545 要求），所以尾巴上有个 Z */
    private static final DateTimeFormatter ICS_STAMP =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);

    private final UserStore users;

    public ReminderService(UserStore users) {
        this.users = users;
    }

    @Transactional(readOnly = true)
    public String ics(long userId) {
        UserStore.ReminderPreference pref = users.reminderPreference(userId)
                .orElse(new UserStore.ReminderPreference(UserStore.DEFAULT_TIMEZONE, null));
        return ics(productName(), pref.timezone(), pref.remindAt(), LocalDate.now(), Instant.now());
    }

    /** 产品名进日历事件的 SUMMARY，所以做成可配的（测试也要能固定它） */
    String productName() {
        return "每日一粒";
    }

    // ==================== 纯函数（可单测，不连数据库） ====================

    /**
     * 生成一份"每天一次"的日历文件（RFC 5545）。
     *
     * <p>几个刻意的决定：
     * <ul>
     *   <li><b>浮动时间</b>（{@code DTSTART;TZID=...}）：用户设的是"每天早上 8 点"，
     *       那就是<b>他所在时区的 8 点</b>。换时区飞一趟，提醒跟着当地时间走才对。</li>
     *   <li><b>没有 UNTIL</b>：不给提醒设终点。日历是用户自己的，想停就自己删，
     *       我们不该替他决定"提醒你 21 天就够了"（§6 那套天数承诺本来就是假的）。</li>
     *   <li><b>DTSTART 用今天</b>而不是固定某年某月：这样导进去立刻就是有效的，不用等到明天。</li>
     *   <li><b>DTSTAMP 用真正的当前时刻（UTC）</b>，不是提醒时间——按 RFC 5545 它是
     *       "这份对象什么时候生成的"，写成提醒时刻会让日历客户端显示一个没发生过的创建时间。</li>
     * </ul>
     */
    public static String ics(String productName, String timezone, LocalTime remindAt, LocalDate today,
                             Instant now) {
        ZoneId zone = zoneOf(timezone);
        LocalTime at = remindAt == null ? LocalTime.parse(DEFAULT_TIME, HHMM) : remindAt;
        LocalTime end = at.plusMinutes(DURATION_MINUTES);

        // 提醒落在 23:5x 时会跨到第二天，事件结束时间得跟着走（否则日历里出现 END 早于 START 的非法事件）
        LocalDate endDate = end.isBefore(at) ? today.plusDays(1) : today;

        List<String> lines = new ArrayList<>();
        lines.add("BEGIN:VCALENDAR");
        lines.add("VERSION:2.0");
        lines.add("PRODID:-//DailySeed//" + productName + "//CN");
        lines.add("CALSCALE:GREGORIAN");
        lines.add("METHOD:PUBLISH");
        lines.add("BEGIN:VEVENT");
        lines.add("UID:dailyseed-" + today.format(ICS_DATE) + "@dailyseed.local");
        lines.add("DTSTAMP:" + ICS_STAMP.format(now));
        lines.add("DTSTART;TZID=" + zone.getId() + ":" + today.format(ICS_DATE) + "T" + at.format(ICS_TIME));
        lines.add("DTEND;TZID=" + zone.getId() + ":" + endDate.format(ICS_DATE) + "T" + end.format(ICS_TIME));
        // 每天一次，永不结束——删不删是用户的事
        lines.add("RRULE:FREQ=DAILY");
        lines.add("SUMMARY:" + escape("今天那一粒 · " + productName));
        lines.add("DESCRIPTION:" + escape("你给自己设的提醒。想停就在日历里把这个日程删掉。"));
        lines.add("TRANSP:TRANSPARENT");
        lines.add("END:VEVENT");
        lines.add("END:VCALENDAR");
        return fold(lines);
    }

    /** 单测用：DTSTAMP 固定成 1970 年，断言就不会被"跑测试的那一刻"影响 */
    static String ics(String productName, String timezone, LocalTime remindAt, LocalDate today) {
        return ics(productName, timezone, remindAt, today, Instant.EPOCH);
    }

    /**
     * 解析用户填的时间。只收 {@code HH:mm}——**故意不用宽松的 {@code LocalTime.parse}**：
     * 它接受 {@code 08:00:00} / {@code 8:00} 这类写法，会让存进库的格式五花八门。
     */
    public static Optional<LocalTime> parseTime(String raw) {
        if (raw == null) {
            return Optional.empty();
        }
        String text = raw.trim();
        if (!text.matches("\\d{2}:\\d{2}")) {
            return Optional.empty();
        }
        try {
            return Optional.of(LocalTime.parse(text, HHMM));
        } catch (DateTimeException e) {
            return Optional.empty(); // 比如 25:00、08:61
        }
    }

    /** 时区名认不出来时退回默认——一个用户写坏的时区不该让整份日历生成失败 */
    static ZoneId zoneOf(String timezone) {
        try {
            return ZoneId.of(timezone == null ? UserStore.DEFAULT_TIMEZONE : timezone);
        } catch (DateTimeException e) {
            return ZoneId.of(UserStore.DEFAULT_TIMEZONE);
        }
    }

    // ==================== iCalendar 语法细节 ====================

    /** 转义 RFC 5545 要求转义的四个字符（反斜杠必须最先替，否则会把后面的转义再转一遍） */
    static String escape(String text) {
        return text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n");
    }

    /**
     * 按 RFC 5545 折行：一行超过 75 个**八位组**就要断开，续行以一个空格开头。
     *
     * <p>这里按 UTF-8 字节数算而不是字符数——中文一个字三个字节，按字符数折会折出
     * 200 多字节的行，严格的日历客户端会解析失败。
     */
    static String fold(List<String> lines) {
        StringBuilder sb = new StringBuilder();
        for (String line : lines) {
            byte[] bytes = line.getBytes(StandardCharsets.UTF_8);
            if (bytes.length <= 75) {
                sb.append(line).append("\r\n");
                continue;
            }
            int used = 0;
            StringBuilder current = new StringBuilder();
            int limit = 75; // 首行 75 字节；续行开头那个空格也算进 75 里，所以正文只剩 74
            for (int i = 0; i < line.length(); ) {
                int cp = line.codePointAt(i);
                String s = new String(Character.toChars(cp));
                int size = s.getBytes(StandardCharsets.UTF_8).length;
                if (used + size > limit) {
                    sb.append(current).append("\r\n ");
                    current.setLength(0);
                    limit = 74;
                    used = 1; // 那个续行空格已经占了 1 字节
                }
                current.append(s);
                used += size;
                i += Character.charCount(cp);
            }
            sb.append(current).append("\r\n");
        }
        return sb.toString();
    }
}
