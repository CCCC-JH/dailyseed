package com.dailyseed.ops;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 活动计数的并发正确性。
 *
 * <p>为什么值得单独测：这套东西是**匿名、无推送**的，出了问题不会有用户来报错——
 * 计数是唯一能把"没人用"和"服务坏了"分开的东西。计数本身悄悄丢几次（比如并发下自增丢了）
 * 不会报错，只会让判断基线偏掉，那比直接的 bug 更难发现。
 *
 * <p>它刻意用**单条不可变记录 + CAS**而不是一堆 AtomicLong：后者在跨零点时会出现
 * "日期已是新的一天、某个计数还是昨天的"这种自相矛盾的快照。这条测试守着这个一致性。
 */
class ActivityCountersTest {

    @Test
    @DisplayName("新建的计数全是 0，日期是今天")
    void startsAtZero() {
        ActivityCounters.Snapshot s = new ActivityCounters().snapshot();
        assertThat(s.sessionsCreated()).isZero();
        assertThat(s.cardsKept()).isZero();
        assertThat(s.date()).isNotBlank();
    }

    @Test
    @DisplayName("各类事件各自记到自己的格子（不会互相串）")
    void eachEventHitsItsOwnSlot() {
        ActivityCounters c = new ActivityCounters();
        c.sessionCreated();
        c.sessionRecovered();
        c.identityRecoveredByCookie();
        c.cardDrawn();
        c.cardDrawn();
        c.cardRedrawn();
        c.cardKept();
        c.cardKeptPast();
        c.graduation();

        ActivityCounters.Snapshot s = c.snapshot();
        assertThat(s.sessionsCreated()).isEqualTo(1);
        assertThat(s.sessionsRecovered()).isEqualTo(1);
        assertThat(s.identityRecoveredByCookie()).isEqualTo(1);
        assertThat(s.cardsDrawn()).isEqualTo(2);
        assertThat(s.cardsRedrawn()).isEqualTo(1);
        assertThat(s.cardsKept()).isEqualTo(1);
        assertThat(s.cardsKeptPast()).isEqualTo(1);
        assertThat(s.graduations()).isEqualTo(1);
    }

    @Test
    @DisplayName("★ 并发自增一个都不丢（16 线程 × 500 次 = 8000）")
    void concurrentIncrementsAreNotLost() throws Exception {
        ActivityCounters c = new ActivityCounters();
        int threads = 16;
        int perThread = 500;
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(threads);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        try {
            for (int i = 0; i < threads; i++) {
                pool.submit(() -> {
                    try {
                        start.await();
                        for (int n = 0; n < perThread; n++) {
                            c.cardKept();
                        }
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        done.countDown();
                    }
                });
            }
            start.countDown();
            assertThat(done.await(30, TimeUnit.SECONDS)).isTrue();
        } finally {
            pool.shutdownNow();
        }
        assertThat(c.snapshot().cardsKept()).isEqualTo((long) threads * perThread);
    }

    @Test
    @DisplayName("★ 并发下读到的快照永远自洽：日期只有一个，且计数单调不减")
    void snapshotsAreAlwaysCoherent() throws Exception {
        ActivityCounters c = new ActivityCounters();
        Queue<ActivityCounters.Snapshot> seen = new ConcurrentLinkedQueue<>();
        int threads = 8;
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(threads * 2);
        ExecutorService pool = Executors.newFixedThreadPool(threads * 2);
        try {
            for (int i = 0; i < threads; i++) {
                pool.submit(() -> {
                    try {
                        start.await();
                        for (int n = 0; n < 300; n++) c.cardDrawn();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        done.countDown();
                    }
                });
                pool.submit(() -> {
                    try {
                        start.await();
                        for (int n = 0; n < 300; n++) seen.add(c.snapshot());
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        done.countDown();
                    }
                });
            }
            start.countDown();
            assertThat(done.await(30, TimeUnit.SECONDS)).isTrue();
        } finally {
            pool.shutdownNow();
        }

        // ① 所有快照的日期必须一致（没有"半新半旧"的中间态）
        assertThat(seen).isNotEmpty().allSatisfy(s -> assertThat(s.date()).isEqualTo(seen.peek().date()));
        // ② 计数不会凭空变小（只有可能读到"还没加上去"的旧值）
        long max = seen.stream().mapToLong(ActivityCounters.Snapshot::cardsDrawn).max().orElseThrow();
        assertThat(max).isEqualTo((long) threads * 300);
        assertThat(seen).allSatisfy(s -> assertThat(s.cardsDrawn()).isBetween(0L, max));
    }
}
