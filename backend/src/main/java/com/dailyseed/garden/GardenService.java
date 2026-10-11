package com.dailyseed.garden;

import com.dailyseed.card.Card;
import com.dailyseed.card.ScienceNotes;
import com.dailyseed.garden.GardenStore.GardenRow;
import com.dailyseed.ops.ActivityCounters;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 我的花园 + 毕业（设计文档 §3.4 / §6）。
 *
 * <p>三条不能破的规则：
 * <ol>
 *   <li><b>只放习惯卡</b>：探索卡属于「探索记录」（§3.2），<b>放纵卡什么都不进</b>（§3.5 红线 5）</li>
 *   <li><b>不做监工</b>：没有"该毕业了"的判定，只有留到 7 次时的一个小标记（§6.1）</li>
 *   <li><b>毕业幂等</b>：重复宣布不报错，也<b>不覆盖</b>第一次的毕业时间</li>
 * </ol>
 */
@Service
public class GardenService {

    /** 毕业入口的小标记阈值（§6.1）：到这个数，「它已经是我的习惯了」这个选项才有意义 */
    static final int GRADUATE_HINT_AT = 7;

    /** 窗台排序：植株大的在前（留得多的先看到）；平局按卡号，顺序稳定，前端不跳 */
    static final Comparator<GardenPlant> ACTIVE_ORDER =
            Comparator.comparingInt(GardenPlant::keptCount).reversed()
                    .thenComparingLong(GardenPlant::cardId);

    /** 已内化清单：刚毕业的在前 */
    static final Comparator<GardenPlant> GRADUATED_ORDER =
            Comparator.comparing(GardenPlant::graduatedAt,
                            Comparator.nullsLast(Comparator.<LocalDateTime>reverseOrder()))
                    .thenComparingLong(GardenPlant::cardId);

    private final GardenStore garden;
    private final ScienceNotes science;
    private final ActivityCounters counters;

    public GardenService(GardenStore garden, ScienceNotes science, ActivityCounters counters) {
        this.garden = garden;
        this.science = science;
        this.counters = counters;
    }

    // ==================== 对外 ====================

    /** 打开花园：窗台上的一排小盆 + 已内化清单（两段分开给，前端不用自己分组） */
    @Transactional(readOnly = true)
    public GardenView garden(long userId) {
        List<GardenPlant> all = garden.rows(userId).stream()
                .filter(GardenService::visibleInGarden)
                .map(this::plant)
                .toList();
        List<GardenPlant> items = all.stream().filter(p -> !p.isGraduated()).sorted(ACTIVE_ORDER).toList();
        List<GardenPlant> graduated = all.stream().filter(GardenPlant::isGraduated).sorted(GRADUATED_ORDER).toList();
        return new GardenView(items.size(), graduated.size(), items, graduated);
    }

    /**
     * 宣布毕业（§6.2）。
     *
     * <p>闸门只有一个：这张卡必须**在花园里**。没留过的卡没有 {@code user_cards} 行，
     * 探索卡和放纵卡被 {@link #visibleInGarden} 拦下——都按"花园里没有这张卡"处理（409），
     * 不给任何"你差一点就能毕业"的暗示。
     *
     * <p>已经是 {@code GRADUATED} 就原样返回（幂等，验收 ②），**不重写毕业时间**。
     */
    @Transactional
    public GardenPlant graduate(long userId, long cardId) {
        GardenRow row = garden.find(userId, cardId)
                .filter(GardenService::visibleInGarden)
                .orElseThrow(() -> new IllegalArgumentException(
                        "花园里没有这张卡——只有留在花园里的习惯卡才能毕业"));
        if (!shouldStampGraduation(row.state())) {
            return plant(row);
        }
        garden.markGraduated(userId, cardId);
        counters.graduation();
        return plant(garden.find(userId, cardId).orElseThrow());
    }

    // ==================== 纯函数（可单测，不连数据库） ====================

    /** 花园里只放习惯卡：探索卡进「探索记录」（§3.2），放纵卡什么都不进（§3.5 / 红线 5） */
    static boolean visibleInGarden(GardenRow row) {
        return Card.HABIT.equals(row.type());
    }

    /** 小标记：留到 7 次 → 「这个选项现在有意义了」，而不是「你该毕业了」（§6.1） */
    static boolean readyToGraduate(int keptCount) {
        return keptCount >= GRADUATE_HINT_AT;
    }

    /** 只有还不是 GRADUATED 的才写毕业时间——这就是幂等的地基，重复宣布覆盖不掉第一次 */
    static boolean shouldStampGraduation(String state) {
        return !GardenPlant.GRADUATED.equals(state);
    }

    // ==================== 组装响应 ====================

    public record GardenView(int plantedCount, int graduatedCount,
                             List<GardenPlant> items, List<GardenPlant> graduated) {
    }

    private GardenPlant plant(GardenRow row) {
        return new GardenPlant(
                row.cardId(),
                row.type(),
                row.category(),
                row.text(),
                row.difficulty(),
                row.keptCount(),
                row.firstKeptAt(),
                row.lastKeptAt(),
                row.state(),
                row.graduatedAt(),
                readyToGraduate(row.keptCount()),
                row.evidenceOrNull(),
                science.get(row.scienceKey()).orElse(null));
    }
}
