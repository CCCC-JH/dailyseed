package com.dailyseed.assignment;

import java.time.LocalDate;
import java.time.LocalDateTime;

/** 每日发放记录。时间字段是 MySQL 的 DATETIME(6)，所以用 LocalDateTime 而不是带时区的类型。 */
public record Assignment(
        long id,
        long userId,
        long cardId,
        LocalDate assignedDate,
        String state,
        LocalDateTime revealedAt,
        int drawCount,
        LocalDateTime keptAt,
        LocalDateTime swappedAt
) {
    public boolean isKept() {
        return "KEPT".equals(state);
    }

    public boolean hasSwapped() {
        return swappedAt != null;
    }

    /** 已揭晓：这张卡翻开给用户看过了（NULL = 还是卡背） */
    public boolean isRevealed() {
        return revealedAt != null;
    }

    /**
     * 一天的发放记录，只填"这一天发了哪张卡给谁"。
     *
     * <p>九字段的 record 直接 new 太容易把日期和卡号写颠倒，测试夹具又天天要造它，
     * 所以给一个语义明确的入口；id 用 0 表示"这只是个夹具，不对应库里任何一行"。
     */
    public static Assignment of(long userId, long cardId, LocalDate date, String state) {
        return new Assignment(0, userId, cardId, date, state, null, 0, null, null);
    }
}
