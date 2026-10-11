package com.dailyseed.assignment;

import static org.assertj.core.api.Assertions.assertThat;

import com.dailyseed.card.Card;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** 分配算法的纯函数测试——不连数据库，跑得快，改算法时是安全网。 */
class AssignmentServiceTest {

    private static Card card(long id, String type, int difficulty) {
        return new Card(id, type, "注意力", "卡 #" + id, difficulty, false, false, null, "why", null, null, null);
    }

    private static List<AssignmentService.Weighted> pool() {
        List<AssignmentService.Weighted> pool = new ArrayList<>();
        for (int i = 1; i <= 42; i++) {
            pool.add(new AssignmentService.Weighted(card(i, Card.HABIT, 1), AssignmentService.typeWeight(Card.HABIT, 42)));
        }
        for (int i = 43; i <= 80; i++) {
            pool.add(new AssignmentService.Weighted(card(i, Card.EXPLORE, 1), AssignmentService.typeWeight(Card.EXPLORE, 38)));
        }
        for (int i = 81; i <= 100; i++) {
            pool.add(new AssignmentService.Weighted(card(i, Card.INDULGE, 0), AssignmentService.typeWeight(Card.INDULGE, 20)));
        }
        return pool;
    }

    @Test
    @DisplayName("同一个种子永远挑到同一张卡——幂等的地基")
    void sameSeedSameCard() {
        List<AssignmentService.Weighted> pool = pool();
        long seed = Objects.hash(42L, "2026-10-08");
        assertThat(AssignmentService.pick(pool, seed).id())
                .isEqualTo(AssignmentService.pick(pool, seed).id());
    }

    @Test
    @DisplayName("类型占比接近 6:3:1，而不是被卡片张数带偏（真实张数是 42:38:20）")
    void typeShareIsNormalized() {
        List<AssignmentService.Weighted> pool = pool();
        int habit = 0;
        int explore = 0;
        int indulge = 0;
        int rounds = 5000;
        for (long seed = 0; seed < rounds; seed++) {
            Card picked = AssignmentService.pick(pool, seed);
            switch (picked.type()) {
                case Card.HABIT -> habit++;
                case Card.EXPLORE -> explore++;
                default -> indulge++;
            }
        }
        assertThat(habit / (double) rounds).isBetween(0.55, 0.65);
        assertThat(explore / (double) rounds).isBetween(0.25, 0.35);
        assertThat(indulge / (double) rounds).isBetween(0.05, 0.15);
    }

    @Test
    @DisplayName("放纵日门槛：累计 5 种 + 冷却 7 天 + 不连抽 + 今天没换过")
    void indulgenceGate() {
        LocalDate today = LocalDate.of(2026, 10, 8);
        assertThat(AssignmentService.canIndulge(4, null, false, false, today)).isFalse();
        assertThat(AssignmentService.canIndulge(5, null, false, false, today)).isTrue();
        assertThat(AssignmentService.canIndulge(9, today.minusDays(6), false, false, today)).isFalse();
        assertThat(AssignmentService.canIndulge(9, today.minusDays(7), false, false, today)).isTrue();
        assertThat(AssignmentService.canIndulge(9, null, true, false, today)).isFalse();
        assertThat(AssignmentService.canIndulge(9, null, false, true, today)).isFalse();
    }

    @Test
    @DisplayName("留得少就压住难度 3——不能让用户挫败")
    void difficultyIsGatedByKeepRate() {
        assertThat(AssignmentService.difficultyMatch(0.1, 3))
                .isLessThan(AssignmentService.difficultyMatch(0.8, 3));
        assertThat(AssignmentService.difficultyMatch(0.1, 3)).isLessThan(1.0);
        assertThat(AssignmentService.difficultyMatch(0.0, 1)).isEqualTo(1.0);
    }

    @Test
    @DisplayName("难度 0 的放纵卡不因为难度被压权重")
    void indulgenceIsNotPenalized() {
        assertThat(AssignmentService.difficultyMatch(0.0, 0)).isEqualTo(1.0);
    }

    @Test
    @DisplayName("补留窗口：3 天含今天——前天还能补，大前天就让它过去")
    void catchUpWindowBoundaries() {
        LocalDate today = LocalDate.of(2026, 10, 9);
        assertThat(AssignmentService.withinCatchUpWindow(today, today, 3)).isTrue();
        assertThat(AssignmentService.withinCatchUpWindow(today.minusDays(1), today, 3)).isTrue();
        assertThat(AssignmentService.withinCatchUpWindow(today.minusDays(2), today, 3)).isTrue();
        assertThat(AssignmentService.withinCatchUpWindow(today.minusDays(3), today, 3)).isFalse();
        assertThat(AssignmentService.withinCatchUpWindow(today.plusDays(1), today, 3)).isFalse();
    }

    // ==================== 抽卡（重抽与配额） ====================

    @Test
    @DisplayName("抽卡配额：0 = 无限；上限到了就抽不动")
    void drawQuota() {
        // 0 与负数都表示无限：这是开发期的默认值
        assertThat(AssignmentService.canDrawAgain(0, 0)).isTrue();
        assertThat(AssignmentService.canDrawAgain(99, 0)).isTrue();
        assertThat(AssignmentService.canDrawAgain(99, -1)).isTrue();
        // 上限 1 = 生产语义：抽过一次就没有重抽
        assertThat(AssignmentService.canDrawAgain(0, 1)).isTrue();
        assertThat(AssignmentService.canDrawAgain(1, 1)).isFalse();
        // 上限 3
        assertThat(AssignmentService.canDrawAgain(2, 3)).isTrue();
        assertThat(AssignmentService.canDrawAgain(3, 3)).isFalse();
    }

    @Test
    @DisplayName("canRedraw：留住了就不能再换（否则一天能攒下好几张）")
    void cannotRedrawAfterKeeping() {
        assertThat(AssignmentService.TodayView.redrawable(false, 1, 0)).isTrue();
        assertThat(AssignmentService.TodayView.redrawable(true, 1, 0)).isFalse();
        assertThat(AssignmentService.TodayView.redrawable(false, 1, 1)).isFalse();
        assertThat(AssignmentService.TodayView.redrawable(false, 0, 1)).isTrue();
    }

    @Test
    @DisplayName("重抽要用不同的种子，否则会抽回同一张")
    void redrawSeedChangesPerRound() {
        long base = Objects.hash(42L, "2026-10-09");
        long round1 = Objects.hash(42L, "2026-10-09", ":draw", 1, 7L);
        long round2 = Objects.hash(42L, "2026-10-09", ":draw", 2, 9L);
        assertThat(round1).isNotEqualTo(base);
        assertThat(round1).isNotEqualTo(round2);
    }

    @Test
    @DisplayName("重抽种子是确定性的——同一轮重试安全，不会每刷新一次换张卡")
    void redrawSeedIsDeterministic() {
        long a = Objects.hash(42L, "2026-10-09", ":draw", 3, 25L);
        long b = Objects.hash(42L, "2026-10-09", ":draw", 3, 25L);
        assertThat(a).isEqualTo(b);
    }

    @Test
    @DisplayName("重抽确实能换到别的卡：池子够大时，不同轮次不总是同一张")
    void redrawPicksVariedCards() {
        List<AssignmentService.Weighted> pool = pool();
        Set<Long> distinct = new HashSet<>();
        for (int round = 1; round <= 20; round++) {
            distinct.add(AssignmentService.pick(pool, Objects.hash(42L, "2026-10-09", ":draw", round, 7L)).id());
        }
        // 20 轮不该只落在一两张上（加权随机 + 不同种子）
        assertThat(distinct.size()).isGreaterThan(3);
    }
}
