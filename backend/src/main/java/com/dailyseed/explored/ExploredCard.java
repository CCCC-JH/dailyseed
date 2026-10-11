package com.dailyseed.explored;

import com.dailyseed.card.Evidence;
import com.dailyseed.card.ScienceNotes;

/**
 * 「走过的」里的一条：一张探索卡 + 你唯一一次遇见它的那天。
 *
 * <p>形状刻意和今天那张、花园那盆保持一致（`?` 都是同一个 {@link Evidence}），
 * 前端只需要认一种依据结构。
 *
 * @param kept  那一天你有没有把它留下——探索卡不强制留住，这里只标一下（§3.2）
 */
public record ExploredCard(
        long cardId,
        String category,
        String text,
        int difficulty,
        String date,
        boolean kept,
        Evidence evidence,
        ScienceNotes.Note science
) {
}
