package com.dailyseed.card;

/**
 * 卡片「?」展开后的四段（设计文档 §3.6）：① 好处 / ② 依据 / ③ 出处，第 ④ 段科普另给。
 *
 * <p>库里 {@code evidence} 是一整段文本（「① …\n② … [\n③ …]」），拆开只是为了让前端排版。
 * <b>没有依据的卡（C 级）返回 null</b>——界面因此不显示「?」入口，宁可少一个入口（红线 3）。
 *
 * <p>放在 card 包而不是某个 Service 里：今天那张、补留列表、花园都用同一个形状，
 * 前端只需要认一种「?」结构。
 */
public record Evidence(String level, String benefit, String basis, String source) {

    /** 卡片版本：没有依据（C 级）就返回 null */
    public static Evidence of(Card card) {
        return card.hasEvidence() ? of(card.evidence(), card.evidenceLevel()) : null;
    }

    /** 没有依据就返回 null——调用方直接把它塞进响应，前端看到 null 就不画入口 */
    public static Evidence of(String evidence, String level) {
        if (evidence == null || evidence.isBlank()) {
            return null;
        }
        String[] parts = evidence.split("\n", 3);
        return new Evidence(
                level,
                parts.length > 0 ? parts[0] : null,
                parts.length > 1 ? parts[1] : null,
                parts.length > 2 ? parts[2] : null);
    }
}
