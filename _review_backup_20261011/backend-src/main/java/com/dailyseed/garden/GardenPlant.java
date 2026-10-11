package com.dailyseed.garden;

import com.dailyseed.card.Evidence;
import com.dailyseed.card.ScienceNotes;
import java.time.LocalDateTime;

/**
 * 花园里的一盆（设计文档 §3.4「窗台 · 一排小盆」）。
 *
 * <p><b>后端不管视觉</b>：{@code keptCount} 交给前端决定植株多大，
 * {@code readyToGraduate} 决定要不要画那个低调的小标记。这里没有任何"你该毕业了"的字段。
 */
public record GardenPlant(
        long cardId,
        String type,
        String category,
        String text,
        int difficulty,
        int keptCount,
        LocalDateTime firstKeptAt,
        LocalDateTime lastKeptAt,
        String state,
        LocalDateTime graduatedAt,
        boolean readyToGraduate,
        Evidence evidence,
        ScienceNotes.Note science
) {

    public static final String ACTIVE = "ACTIVE";
    public static final String GRADUATED = "GRADUATED";

    /**
     * 是不是已经毕业了。**故意不是 public**：Jackson 只序列化 public 的 getter，
     * 所以响应里不会多出一个和 {@code state} 重复的 {@code graduated} 字段——
     * 状态看 {@code state}，分组看 {@code items} / {@code graduated} 两个数组，各管一件事。
     */
    boolean isGraduated() {
        return GRADUATED.equals(state);
    }
}
