package com.dailyseed.ops;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.stereotype.Component;

/**
 * 今天的活动量——**零 PII**，只有计数。
 *
 * <p>为什么需要它：这个产品是匿名、无推送、无账号的，所以**没有任何用户会来报错**。
 * 出了问题你只会看到"没人用"，而"没人用"和"服务坏了"从外部看起来一模一样。
 * 一组按天的计数能把这两件事分开，而且不需要碰任何个人数据。
 *
 * <p>三条刻意的边界：
 * <ol>
 *   <li><b>不记是谁</b>：没有 userId、没有 deviceId、没有同步码。只有一个数字加一</li>
 *   <li><b>不记累计</b>：只看今天。累计数会变成"增长指标"，而那是产品红线 1 的另一面——
 *       我们不做监工，也不该给自己造一个监工 dashboard</li>
 *   <li><b>不持久化</b>：进程重启就归零。它就是"看一眼现在怎么样"，不是分析数据</li>
 * </ol>
 *
 * <p>时间用固定的 {@code Asia/Shanghai}（默认用户时区）判"今天"——这是内部运维指标，
 * 不值得为它去查每个用户的时区。"今天"翻转时自动归零。
 */
@Component
public class ActivityCounters {

    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    public record Snapshot(
            String date,
            long sessionsCreated,
            long sessionsRecovered,
            long identityRecoveredByCookie,
            long cardsDrawn,
            long cardsRedrawn,
            long cardsKept,
            long cardsKeptPast,
            long graduations
    ) {
    }

    private record Counts(
            long sessionsCreated,
            long sessionsRecovered,
            long identityRecoveredByCookie,
            long cardsDrawn,
            long cardsRedrawn,
            long cardsKept,
            long cardsKeptPast,
            long graduations
    ) {
        Counts plus(Counts other) {
            return new Counts(
                    sessionsCreated + other.sessionsCreated,
                    sessionsRecovered + other.sessionsRecovered,
                    identityRecoveredByCookie + other.identityRecoveredByCookie,
                    cardsDrawn + other.cardsDrawn,
                    cardsRedrawn + other.cardsRedrawn,
                    cardsKept + other.cardsKept,
                    cardsKeptPast + other.cardsKeptPast,
                    graduations + other.graduations);
        }
    }

    private static final Counts ZERO = new Counts(0, 0, 0, 0, 0, 0, 0, 0);

    private record Day(LocalDate date, Counts counts) {
    }

    /**
     * 单个原子引用持有"哪一天 + 那几个数"。
     *
     * <p>不用 8 个 {@code AtomicLong}：那样"今天"和各个计数会在跨零点的瞬间各自翻转，
     * 出现"日期已是新的一天、但某个计数还是昨天的"这种自相矛盾的快照。
     * 换成一个不可变记录整体 CAS，读到的东西永远是一致的。
     */
    private final AtomicReference<Day> state = new AtomicReference<>(new Day(LocalDate.now(ZONE), ZERO));

    /** 今天。跨零点时先翻页再累加，翻页与累加在同一个 CAS 循环里完成，不会丢 */
    private void add(Counts delta) {
        while (true) {
            Day current = state.get();
            LocalDate today = LocalDate.now(ZONE);
            Counts base = current.date().equals(today) ? current.counts() : ZERO;
            if (state.compareAndSet(current, new Day(today, base.plus(delta)))) {
                return;
            }
        }
    }

    // ==================== 记什么（都只 +1） ====================

    public void sessionCreated() {
        add(new Counts(1, 0, 0, 0, 0, 0, 0, 0));
    }

    /** 用同步码找回了一个身份 */
    public void sessionRecovered() {
        add(new Counts(0, 1, 0, 0, 0, 0, 0, 0));
    }

    /** 浏览器缓存被清掉、靠 Cookie 认回了人——这条最值得看，它是退路真的救到人的次数 */
    public void identityRecoveredByCookie() {
        add(new Counts(0, 0, 1, 0, 0, 0, 0, 0));
    }

    /** 抽（含第一次揭晓） */
    public void cardDrawn() {
        add(new Counts(0, 0, 0, 1, 0, 0, 0, 0));
    }

    /** 重抽——它和"抽"分开数：重抽占比是"卡片合不合适"最直接的信号 */
    public void cardRedrawn() {
        add(new Counts(0, 0, 0, 0, 1, 0, 0, 0));
    }

    public void cardKept() {
        add(new Counts(0, 0, 0, 0, 0, 1, 0, 0));
    }

    public void cardKeptPast() {
        add(new Counts(0, 0, 0, 0, 0, 0, 1, 0));
    }

    public void graduation() {
        add(new Counts(0, 0, 0, 0, 0, 0, 0, 1));
    }

    public Snapshot snapshot() {
        Day current = state.get();
        LocalDate today = LocalDate.now(ZONE);
        Counts c = current.date().equals(today) ? current.counts() : ZERO;
        return new Snapshot(today.toString(), c.sessionsCreated(), c.sessionsRecovered(),
                c.identityRecoveredByCookie(), c.cardsDrawn(), c.cardsRedrawn(),
                c.cardsKept(), c.cardsKeptPast(), c.graduations());
    }
}
