package com.dailyseed.explored;

import com.dailyseed.assignment.Assignment;
import com.dailyseed.assignment.AssignmentStore;
import com.dailyseed.card.Card;
import com.dailyseed.card.CardStore;
import com.dailyseed.card.Evidence;
import com.dailyseed.card.ScienceNotes;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 探索记录（设计文档 §3.2 / §3.3）。
 *
 * <p>三类卡各进各的家，这条线是产品结构本身：
 * <ul>
 *   <li>习惯卡 → 我的花园（{@code GardenService.visibleInGarden}）</li>
 *   <li>探索卡 → <b>这里</b>，一次性，只记"你走过"</li>
 *   <li>放纵卡 → 什么都不进（§3.5 红线 5）</li>
 * </ul>
 *
 * <p><b>这一页不是成就册。</b>它是给用户自己回看的路，所以：
 * 没有连续天数、没有进度条、没有徽章、没有"你还差几张"——
 * 只有一份安静的清单和一句"这些是你走过的 N 条路"（红线 1）。
 */
@Service
public class ExploredService {

    /** 每位用户一天只有一行发放记录，所以"全部历史"就是 daily_assignments 全表按用户过滤 */
    private final AssignmentStore assignments;
    private final CardStore cards;
    private final ScienceNotes science;

    public ExploredService(AssignmentStore assignments, CardStore cards, ScienceNotes science) {
        this.assignments = assignments;
        this.cards = cards;
        this.science = science;
    }

    @Transactional(readOnly = true)
    public ExploredView explored(long userId) {
        // 新的在前（AssignmentStore.findAll 的排序），所以下面不用再排一次
        List<Assignment> history = assignments.findAll(userId);
        Map<Long, Assignment> unique = dedupeByCard(history);
        Map<Long, Card> catalog = cards.findByIds(unique.keySet());

        List<ExploredCard> items = new ArrayList<>();
        for (Assignment a : unique.values()) {
            Card card = catalog.get(a.cardId());
            // 两张闸门：卡没被删掉；且真的是探索卡（放纵卡/习惯卡一张都不许从这条路漏出去）
            if (card != null && visibleInExplored(card.type())) {
                items.add(item(a, card));
            }
        }

        String to = items.isEmpty() ? null : items.get(0).date();
        String from = items.isEmpty() ? null : items.get(items.size() - 1).date();
        return new ExploredView(items.size(), from, to, items);
    }

    // ==================== 纯函数（可单测，不连数据库） ====================

    /**
     * 同一张探索卡只留**最后一次**遇见它的记录。
     *
     * <p>去重不是洁癖：重抽会把当天那行换成别的卡，同一张卡理论上可以在不同日子各出现一次。
     * 保留最新那次——这一页记的是"我和这张卡的关系"，重复列出来就变成流水账了。
     *
     * <p>入参要求**新的在前**，用 {@link LinkedHashMap} 落位，输出天然也是新的在前。
     */
    static Map<Long, Assignment> dedupeByCard(List<Assignment> history) {
        Map<Long, Assignment> first = new LinkedHashMap<>();
        for (Assignment a : history) {
            first.putIfAbsent(a.cardId(), a);
        }
        return first;
    }

    /** 严闸：不是探索卡的，一张都不许从这条路漏出去（放纵卡更不能，红线 5） */
    static boolean visibleInExplored(String type) {
        return Card.EXPLORE.equals(type);
    }

    // ==================== 组装响应 ====================

    /** 走过的全部探索卡；{@code from} / {@code to} 为空表示一次都还没走过 */
    public record ExploredView(int totalCount, String from, String to, List<ExploredCard> items) {
    }

    private ExploredCard item(Assignment a, Card card) {
        return new ExploredCard(
                card.id(),
                card.category(),
                card.text(),
                card.difficulty(),
                a.assignedDate().toString(),
                a.isKept(),
                Evidence.of(card),
                science.get(card.scienceKey()).orElse(null));
    }
}
