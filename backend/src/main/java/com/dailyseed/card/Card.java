package com.dailyseed.card;

/**
 * 一张卡。
 *
 * @param evidence      展示给用户的依据（① 好处 + ② 依据 [+ ③ 出处]），为空则界面不显示「?」
 * @param evidenceLevel A 研究 / B 机制 / NULL（= C，无依据）
 * @param scienceKey    指向 science-notes.json 的科普条目（第 ④ 段）
 */
public record Card(
        long id,
        String type,
        String category,
        String text,
        int difficulty,
        boolean photoHint,
        boolean shareable,
        String indulgenceKind,
        String why,
        String evidence,
        String evidenceLevel,
        String scienceKey
) {

    public static final String HABIT = "HABIT";
    public static final String EXPLORE = "EXPLORE";
    public static final String INDULGE = "INDULGE";

    /** 放纵卡：零消耗、不可留着、不进花园、不可毕业（设计文档 §3.5） */
    public boolean isIndulgence() {
        return INDULGE.equals(type);
    }

    /** 界面是否显示「?」——C 级（没依据）就不显示，宁可少一个入口 */
    public boolean hasEvidence() {
        return evidence != null && !evidence.isBlank();
    }
}
