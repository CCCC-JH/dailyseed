package com.dailyseed.garden;

import static org.assertj.core.api.Assertions.assertThat;

import com.dailyseed.card.Card;
import com.dailyseed.garden.GardenStore.GardenRow;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 花园的纯函数测试——不连数据库，跑得快。
 *
 * <p>「放纵卡绝不出现」这条红线**刻意由这里的 {@link GardenService#visibleInGarden} 守着**，
 * 而不是靠 SQL 里的 WHERE：纯函数改了会红，SQL 改了没人知道。
 */
class GardenServiceTest {

    private static GardenRow row(long cardId, String type, int keptCount, String state, LocalDateTime graduatedAt) {
        return new GardenRow(cardId, type, "注意力", "卡 #" + cardId, 1, keptCount,
                LocalDateTime.of(2026, 9, 12, 8, 31), LocalDateTime.of(2026, 10, 8, 21, 0),
                state, graduatedAt, null, null, null);
    }

    private static GardenPlant plant(long cardId, int keptCount, LocalDateTime graduatedAt) {
        return new GardenPlant(cardId, Card.HABIT, "注意力", "卡 #" + cardId, 1, keptCount,
                null, null,
                graduatedAt == null ? GardenPlant.ACTIVE : GardenPlant.GRADUATED, graduatedAt,
                keptCount >= 7, null, null);
    }

    @Test
    @DisplayName("★ 放纵卡绝不进花园，探索卡也不进（§3.2 属探索记录 / §3.5 红线 5）")
    void onlyHabitCardsAreVisible() {
        assertThat(GardenService.visibleInGarden(row(1, Card.HABIT, 3, "ACTIVE", null))).isTrue();
        assertThat(GardenService.visibleInGarden(row(81, Card.INDULGE, 1, "ACTIVE", null))).isFalse();
        assertThat(GardenService.visibleInGarden(row(43, Card.EXPLORE, 1, "ACTIVE", null))).isFalse();
    }

    @Test
    @DisplayName("毕业标记：留到 7 次才出现——「这个选项有意义了」，不是「你该毕业了」")
    void graduationHintAppearsAtSeven() {
        assertThat(GardenService.readyToGraduate(6)).isFalse();
        assertThat(GardenService.readyToGraduate(7)).isTrue();
        assertThat(GardenService.readyToGraduate(34)).isTrue();
    }

    @Test
    @DisplayName("★ 幂等的地基：已经毕业的不再写时间——重复宣布覆盖不掉第一次的毕业时间")
    void graduationStampIsWrittenOnlyOnce() {
        assertThat(GardenService.shouldStampGraduation(GardenPlant.ACTIVE)).isTrue();
        assertThat(GardenService.shouldStampGraduation(GardenPlant.GRADUATED)).isFalse();
    }

    @Test
    @DisplayName("窗台排序：留得多的在前，平局按卡号（顺序稳定，前端不会跳）")
    void activeOrderIsStable() {
        List<GardenPlant> sorted = List.of(
                        plant(9, 3, null), plant(4, 21, null), plant(7, 21, null), plant(1, 1, null))
                .stream().sorted(GardenService.ACTIVE_ORDER).toList();
        assertThat(sorted).extracting(GardenPlant::cardId).containsExactly(4L, 7L, 9L, 1L);
    }

    @Test
    @DisplayName("已内化清单：刚毕业的在前，同一时刻按卡号")
    void graduatedOrderIsNewestFirst() {
        LocalDateTime sameMoment = LocalDateTime.of(2026, 10, 9, 12, 0);
        List<GardenPlant> sorted = List.of(
                        plant(1, 5, LocalDateTime.of(2026, 9, 1, 9, 0)),
                        plant(3, 9, sameMoment),
                        plant(2, 9, sameMoment))
                .stream().sorted(GardenService.GRADUATED_ORDER).toList();
        assertThat(sorted).extracting(GardenPlant::cardId).containsExactly(2L, 3L, 1L);
    }
}
