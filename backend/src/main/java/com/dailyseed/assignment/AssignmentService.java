package com.dailyseed.assignment;

import com.dailyseed.card.Card;
import com.dailyseed.card.CardStore;
import com.dailyseed.card.Evidence;
import com.dailyseed.card.ScienceNotes;
import com.dailyseed.ops.ActivityCounters;
import com.dailyseed.user.UserStore;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Random;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 每日分配（设计文档 §5）。
 *
 * <p>三条不能破的规则：
 * <ol>
 *   <li><b>幂等</b>：同一用户同一天永远得到同一张卡（种子 = hash(userId, date)）</li>
 *   <li><b>懒生成</b>：点开才算，不需要定时任务</li>
 *   <li><b>放纵日门槛不公示</b>：门槛存在，但界面上不显示进度</li>
 * </ol>
 */
@Service
public class AssignmentService {

    /** 运行时目标占比（设计文档 §5.3）——按类型归一化，避免被卡片数量带偏 */
    private static final Map<String, Double> TYPE_SHARE = Map.of(
            Card.HABIT, 0.6,
            Card.EXPLORE, 0.3,
            Card.INDULGE, 0.1);

    private static final int RECENT_ASSIGN_DAYS = 30;
    private static final int INDULGE_MIN_KEPT_KINDS = 5;
    private static final int INDULGE_COOLDOWN_DAYS = 7;

    /**
     * 每天最多抽几次（含第一次）。<b>0 = 无限</b>，开发期默认无限，方便连着抽看算法与手感。
     *
     * <p>生产语义是 1（只能抽一次、没有重抽）；改配置即可切回去，不必动代码。
     */
    private final int maxDrawsPerDay;

    private final CardStore cards;
    private final AssignmentStore assignments;
    private final UserStore users;
    private final ScienceNotes science;
    private final ActivityCounters counters;

    public AssignmentService(CardStore cards, AssignmentStore assignments, UserStore users,
                             ScienceNotes science, ActivityCounters counters,
                             @Value("${dailyseed.draw.max-per-day:0}") int maxDrawsPerDay) {
        this.cards = cards;
        this.assignments = assignments;
        this.users = users;
        this.science = science;
        this.counters = counters;
        this.maxDrawsPerDay = maxDrawsPerDay;
    }

    // ==================== 对外 ====================

    @Transactional
    public TodayView today(long userId) {
        LocalDate today = todayOf(userId);
        Assignment assignment = assignments.findByDate(userId, today)
                .orElseGet(() -> assignments.insertIfAbsent(userId, pickForToday(userId, today).id(), today, 0));
        Card card = cards.findById(assignment.cardId()).orElseThrow();
        return view(userId, today, assignment, card, canIndulge(userId, today));
    }

    /**
     * 抽：第一次抽 = 选中当天那张并揭晓；之后每次 = <b>换掉当天那张</b>（重抽）。
     *
     * <p>没留住的旧卡直接丢——语义是"换一个更合适的"，不是"攒着备用"。
     * 幂等前提没有变：daily_assignments 仍然一天一行，重抽只是换掉那一行的 card_id。
     *
     * <p>把 {@code getView} 传成 true 就只读当前状态（前端刷新时用，不消耗配额）。
     */
    @Transactional
    public TodayView draw(long userId, boolean getView) {
        LocalDate today = todayOf(userId);
        Assignment existing = assignments.findByDate(userId, today).orElse(null);

        if (getView && existing != null) {
            Card current = cards.findById(existing.cardId()).orElseThrow();
            return view(userId, today, existing, current, canIndulge(userId, today));
        }

        if (existing == null) {
            // 第一次抽：懒生成 + 直接标记已揭晓与抽卡次数
            long cardId = pickForToday(userId, today, null).id();
            Assignment created = assignments.insertIfAbsent(userId, cardId, today, 1);
            assignments.markRevealed(created.id());
            Assignment fresh = assignments.findByDate(userId, today).orElseThrow();
            Card card = cards.findById(fresh.cardId()).orElseThrow();
            counters.cardDrawn();
            return view(userId, today, fresh, card, canIndulge(userId, today));
        }

        if (!existing.isRevealed()) {
            // 懒生成过但还没揭晓（比如只是 GET /api/today 过）：揭晓就算第一次抽
            assignments.markDrawn(existing.id());
            Assignment revealed = assignments.findByDate(userId, today).orElseThrow();
            Card card = cards.findById(revealed.cardId()).orElseThrow();
            counters.cardDrawn();
            return view(userId, today, revealed, card, canIndulge(userId, today));
        }

        // 重抽：已留住的不能再换（否则一天能攒下好几张），配额用完也不行
        if (existing.isKept()) {
            throw new IllegalStateException("这张已经留住了，就不再换了");
        }
        if (!canDrawAgain(existing.drawCount(), maxDrawsPerDay)) {
            throw new IllegalStateException("今天的抽卡次数用完了");
        }

        Card picked = pickForToday(userId, today, existing.cardId());
        // 条件更新：只在 draw_count 还是我们读到的那个值时才生效。
        // 并发时只有一个请求能改到行，其余的重读之后重算——否则 N 次并发重抽只会 +1 次计数。
        if (!assignments.redraw(existing.id(), picked.id(), existing.drawCount())) {
            return redrawAfterRace(userId, today, 0);
        }
        Assignment redrawn = assignments.findByDate(userId, today).orElseThrow();
        Card card = cards.findById(redrawn.cardId()).orElseThrow();
        counters.cardRedrawn(); // 和"抽"分开数：重抽占比是卡片合不合适最直接的信号
        return view(userId, today, redrawn, card, canIndulge(userId, today));
    }

    /**
     * 条件更新输给了并发请求之后：重读最新状态，再决定是"重试一次"还是"如实返回"。
     *
     * <p>三条分支都要有，不然会掉进两种坑：
     * <ul>
     *   <li>对方换了张卡 → 我们手上的 {@code existing} 已经过时，**必须重算**（不能拿旧种子再抽一次，
     *       那会抽到和对方一样的卡，用户会觉得"点了没反应"）</li>
     *   <li>对方**留住了** → 这时候不能再换（留下来的东西不能被抽走），如实返回</li>
     *   <li>配额被对方用完了 → 抛 409，和单线程时的口径一致</li>
     * </ul>
     *
     * @param depth 已经退让过几次。设个上限是为了**有界**：极端情况下（很多请求同时抢）
     *              递归理论上会一直让下去，而一个没有上界的重试循环在故障时最难查。
     *              到这个上限就如实返回当前状态——对用户来说只是"这次没换成"。
     */
    private TodayView redrawAfterRace(long userId, LocalDate today, int depth) {
        Assignment latest = assignments.findByDate(userId, today).orElseThrow();
        Card card = cards.findById(latest.cardId()).orElseThrow();
        if (latest.isKept() || !canDrawAgain(latest.drawCount(), maxDrawsPerDay) || depth >= 3) {
            return view(userId, today, latest, card, canIndulge(userId, today));
        }
        Card picked = pickForToday(userId, today, latest.cardId());
        if (!assignments.redraw(latest.id(), picked.id(), latest.drawCount())) {
            return redrawAfterRace(userId, today, depth + 1);
        }
        Assignment redrawn = assignments.findByDate(userId, today).orElseThrow();
        Card winner = cards.findById(redrawn.cardId()).orElseThrow();
        counters.cardRedrawn();
        return view(userId, today, redrawn, winner, canIndulge(userId, today));
    }

    /** 还能不能再抽一次。{@code maxDraws <= 0} 表示无限（开发期默认）。 */
    static boolean canDrawAgain(int drawCount, int maxDraws) {
        return maxDraws <= 0 || drawCount < maxDraws;
    }

    @Transactional
    public TodayView keep(long userId, String note) {
        LocalDate today = todayOf(userId);
        Assignment assignment = assignments.findByDate(userId, today)
                .orElseThrow(() -> new IllegalStateException("今天还没有卡"));
        Card card = cards.findById(assignment.cardId()).orElseThrow();
        if (card.isIndulgence()) {
            throw new IllegalArgumentException("放纵卡不用「留着」——它不需要被保留");
        }
        // 已经留过就原样返回。留着是唯一的核心交互，双击/重试不该把它越点越大——
        // keptCount 还驱动「毕业小标记 ≥7」（§6.1）和放纵日门槛，点大了就是产品语义坏了。
        //
        // ⚠️ 这里这个读检查**挡不住并发**：并发的 8 个请求能同时读到 PENDING、同时走到下面。
        //    真正的闸门是 markKept 的 `WHERE state <> 'KEPT'`——它保证只有一个请求返回 true，
        //    也就只有一个请求会去加 kept_count。所以 addKept **必须**由返回值把关。
        //    （实测：不加这道闸时并发 8 次「留着」会把 kept_count 加到 5~7。）
        if (assignment.isKept()) {
            return view(userId, today, assignment, card, canIndulge(userId, today));
        }
        if (!assignments.markKept(assignment.id())) {
            // 被并发请求抢先了：它已经完成了这次留住（也加过计数了），
            // 这里只把最新状态读回来返回——**不能**再记一次活动计数，否则计数会比真实留住次数大
            Assignment done = assignments.findByDate(userId, today).orElseThrow();
            return view(userId, today, done, card, canIndulge(userId, today));
        }
        assignments.addKept(userId, card.id());
        Assignment kept = assignments.findByDate(userId, today).orElseThrow();
        counters.cardKept();
        return view(userId, today, kept, card, canIndulge(userId, today));
    }

    /** 放纵日：主动把今天换成一张放纵卡（每天最多一次） */
    @Transactional
    public TodayView indulge(long userId) {
        LocalDate today = todayOf(userId);
        if (!canIndulge(userId, today)) {
            throw new IllegalStateException("今天不能换放纵卡");
        }
        Assignment assignment = assignments.findByDate(userId, today)
                .orElseThrow(() -> new IllegalStateException("今天还没有卡"));
        Card picked = pickIndulgence(userId, today);
        assignments.swapCard(assignment.id(), picked.id());
        Assignment swapped = assignments.findByDate(userId, today).orElseThrow();
        return view(userId, today, swapped, picked, false);
    }

    // ==================== 补留（最近 3 天，含今天） ====================

    /** 补留窗口天数（设计文档 §3.3） */
    static final int CATCH_UP_DAYS = 3;

    /** 纯函数：可补留的日期区间是 [today-(days-1), today] */
    static boolean withinCatchUpWindow(LocalDate date, LocalDate today, int days) {
        return !date.isAfter(today) && !date.isBefore(today.minusDays(days - 1L));
    }

    /** 最近 N 天（含今天）的发放记录，供「补留」列表用 */
    @Transactional(readOnly = true)
    public List<HistoryItem> history(long userId, int days) {
        LocalDate today = todayOf(userId);
        int window = Math.min(Math.max(days, 1), CATCH_UP_DAYS);
        return assignments.findBetween(userId, today.minusDays(window - 1L), today).stream()
                .map(a -> item(a, cards.findById(a.cardId()).orElseThrow()))
                .toList();
    }

    /**
     * 补留：把过去没留的卡留下。
     *
     * <p>三道闸：只能补**自己的**、**3 天内**的；放纵卡不走这条路（它不需要被保留）。
     *
     * <p><b>为什么「已经留过」返回 409 而不是像今天那样幂等返回</b>：
     * 补留列表里已经留住的那几条**根本不画「补留」按钮**，所以能走到这里的"已经留过"
     * 只有两种可能——手改了请求，或者**两个请求同时点**。前者该被拒绝；
     * 后者在下面用 {@link AssignmentStore#markKept} 的返回值处理掉（返回当前状态，不重复加计数），
     * 两条路都不需要用户看到红字。`verify_api.py` 的 A13 守着串行那一条。
     */
    @Transactional
    public HistoryItem keepPast(long userId, long assignmentId) {
        LocalDate today = todayOf(userId);
        Assignment assignment = assignments.findById(assignmentId)
                .filter(a -> a.userId() == userId)
                .orElseThrow(() -> new IllegalArgumentException("找不到这条发放记录"));
        Card card = cards.findById(assignment.cardId()).orElseThrow();

        if (card.isIndulgence()) {
            throw new IllegalArgumentException("放纵卡不用「留着」");
        }
        if (assignment.isKept()) {
            throw new IllegalStateException("这张已经留过了");
        }
        if (!withinCatchUpWindow(assignment.assignedDate(), today, CATCH_UP_DAYS)) {
            throw new IllegalStateException("超过 " + CATCH_UP_DAYS + " 天了，就让它过去吧");
        }

        // 和今天那条路同一道闸：只有真的改到行的请求才去加计数，并发时另一个请求只重读状态。
        // 不加这道闸的话，两个并发补留会把 kept_count 加两次（同一张卡同一天留了两遍）。
        if (!assignments.markKept(assignment.id())) {
            return item(assignments.findById(assignment.id()).orElseThrow(), card);
        }
        assignments.addKept(userId, card.id());

        // 必须重读：markKept 之后旧对象里的 state 还是 PENDING，直接返回会让客户端以为没留上
        Assignment updated = assignments.findById(assignment.id()).orElseThrow();
        counters.cardKeptPast();
        return item(updated, card);
    }

    // ==================== 选卡 ====================

    private Card pickForToday(long userId, LocalDate today) {
        return pickForToday(userId, today, null);
    }

    /**
     * 选今天那张卡。
     *
     * <p>{@code excludeCardId} 非空时是<b>重抽</b>：把当前这张排除掉，保证抽到的确实换了张。
     * 种子带上当前抽卡次数，所以同一轮重抽是确定性的、重试安全，而不同轮会真的换卡。
     */
    private Card pickForToday(long userId, LocalDate today, Long excludeCardId) {
        Assignment current = excludeCardId == null
                ? assignments.findByDate(userId, today).orElse(null)
                : null;
        int round = current == null ? 0 : current.drawCount();

        List<Card> pool = candidates(userId, today, excludeCardId);
        List<Weighted> weighted = weigh(userId, today, pool);
        long seed = excludeCardId == null
                ? Objects.hash(userId, today.toString())
                : Objects.hash(userId, today.toString(), ":draw", round, excludeCardId);
        return pick(weighted, seed);
    }

    private Card pickIndulgence(long userId, LocalDate today) {
        Set<Long> excluded = new HashSet<>(cards.graduatedCardIds(userId));
        excluded.addAll(cards.assignedCardIdsSince(userId, today.minusDays(RECENT_ASSIGN_DAYS)));
        List<Card> pool = cards.activeCards().stream()
                .filter(Card::isIndulgence)
                .filter(c -> !excluded.contains(c.id()))
                .sorted(Comparator.comparingLong(Card::id))
                .toList();
        if (pool.isEmpty()) {
            throw new IllegalStateException("没有可发的放纵卡（都发过了）");
        }
        List<Weighted> weighted = pool.stream().map(c -> new Weighted(c, 1.0)).toList();
        // 换卡也用确定性种子，重试安全（§5.5）
        return pick(weighted, Objects.hash(userId, today + ":indulge"));
    }

    /** 硬约束 + 软约束（§5.2）：候选不足时先放宽"不连续同类/交替类型"，再放宽 30 天窗口 */
    private List<Card> candidates(long userId, LocalDate today) {
        return candidates(userId, today, null);
    }

    /**
     * @param excludeCardId 重抽时排除当前这张。注意它只是**优先级最低**的约束：
     *                      如果排除后池子空了（比如卡都快发完了），宁可重复也不发不出去。
     */
    private List<Card> candidates(long userId, LocalDate today, Long excludeCardId) {
        Set<Long> excluded = new HashSet<>(cards.graduatedCardIds(userId));
        excluded.addAll(cards.assignedCardIdsSince(userId, today.minusDays(RECENT_ASSIGN_DAYS)));
        boolean canIndulge = canIndulge(userId, today);
        Optional<Card> yesterday = cards.cardOfDate(userId, today.minusDays(1));

        List<Card> base = cards.activeCards().stream()
                .filter(c -> !excluded.contains(c.id()))
                .filter(c -> !c.isIndulgence() || canIndulge)
                .toList();

        List<Card> alternated = base.stream()
                .filter(c -> yesterday.map(y -> !y.category().equals(c.category())).orElse(true))
                .filter(c -> yesterday.map(y -> !y.type().equals(c.type())).orElse(true))
                .toList();

        List<Card> pool = alternated.isEmpty() ? base : alternated;
        if (pool.isEmpty()) {
            // 极端情况：30 天窗口内把池子掏空了 —— 放宽窗口，但绝不发已毕业的
            Set<Long> graduated = cards.graduatedCardIds(userId);
            pool = cards.activeCards().stream()
                    .filter(c -> !graduated.contains(c.id()))
                    .filter(c -> !c.isIndulgence() || canIndulge)
                    .toList();
        }
        // 重抽：把当前这张拿掉，但拿掉之后不能空
        if (excludeCardId != null) {
            List<Card> withoutCurrent = pool.stream()
                    .filter(c -> c.id() != excludeCardId)
                    .toList();
            if (!withoutCurrent.isEmpty()) {
                pool = withoutCurrent;
            }
        }
        return pool.stream().sorted(Comparator.comparingLong(Card::id)).toList();
    }

    private List<Weighted> weigh(long userId, LocalDate today, List<Card> pool) {
        Map<Long, Integer> kept = cards.keptCounts(userId);
        Map<Long, LocalDate> lastSeen = cards.lastAssignedDates(userId, today.minusDays(60));
        Map<String, Long> countByType = pool.stream()
                .collect(java.util.stream.Collectors.groupingBy(Card::type, java.util.stream.Collectors.counting()));
        double recentKeepRate = keepRate(kept);

        List<Weighted> out = new ArrayList<>(pool.size());
        for (Card card : pool) {
            long daysSince = Optional.ofNullable(lastSeen.get(card.id()))
                    .map(d -> ChronoUnit.DAYS.between(d, today))
                    .orElse(60L);   // 60 天没见过 = 权重上限
            double w = weight(card, kept.getOrDefault(card.id(), 0), daysSince, recentKeepRate,
                    countByType.getOrDefault(card.type(), 1L));
            out.add(new Weighted(card, w));
        }
        return out;
    }

    private static double keepRate(Map<Long, Integer> kept) {
        if (kept.isEmpty()) {
            return 0.5;
        }
        long keptTimes = kept.values().stream().mapToLong(Integer::longValue).sum();
        return Math.min(1.0, keptTimes / (double) (kept.size() * 3));
    }

    // ==================== 纯函数（可单测） ====================

    record Weighted(Card card, double weight) {
    }

    /** 加权随机：同一个种子永远得到同一张
     *
     * <p>用 {@link java.util.SplittableRandom} 而不是 {@code java.util.Random}：
     * 后者在**相邻种子**下首个 {@code nextDouble()} 高度相关（实测占比会跑偏），
     * 而这里必须保证不同用户、相邻日期的种子都能均匀落点。
     */
    static Card pick(List<Weighted> pool, long seed) {
        double total = pool.stream().mapToDouble(Weighted::weight).sum();
        double r = new java.util.SplittableRandom(seed).nextDouble() * total;
        double acc = 0;
        for (Weighted w : pool) {
            acc += w.weight();
            if (r < acc) {
                return w.card();
            }
        }
        return pool.get(pool.size() - 1).card();
    }

    /** 软权重（§5.3）：留过的更容易再出现 + 太久没见的略微加权 + 难度匹配 + 类型占比 */
    static double weight(Card card, int keptCount, long daysSinceLastAssign, double recentKeepRate, long sameTypeCount) {
        double w = 1.0;
        w *= 1 + Math.log1p(keptCount) * 2.0;
        w *= 1 + Math.min(daysSinceLastAssign, 60) / 60.0 * 0.5;
        w *= difficultyMatch(recentKeepRate, card.difficulty());
        w *= typeWeight(card.type(), sameTypeCount);
        return w;
    }

    /** 留得稳 → 允许上难度；留得少 → 压住难度 3（§5.3 的简化实现） */
    static double difficultyMatch(double recentKeepRate, int difficulty) {
        return switch (difficulty) {
            case 0, 1 -> 1.0;
            case 2 -> recentKeepRate >= 0.4 ? 1.1 : 0.9;
            default -> recentKeepRate >= 0.6 ? 1.2 : 0.3;
        };
    }

    /** 按类型归一化，让实际发放接近 6:3:1，而不是被卡片张数带偏 */
    static double typeWeight(String type, long sameTypeCount) {
        if (sameTypeCount <= 0) {
            return 1.0;
        }
        return TYPE_SHARE.getOrDefault(type, 1.0) / sameTypeCount;
    }

    /** 放纵日门槛（§5.5）：累计留住过 ≥5 种 + 冷却 7 天 + 不连抽 + 今天没换过。全部不公示。 */
    static boolean canIndulge(int keptKinds, LocalDate lastIndulgence, boolean yesterdayWasIndulgence,
                              boolean alreadySwappedToday, LocalDate today) {
        if (alreadySwappedToday || yesterdayWasIndulgence) {
            return false;
        }
        if (keptKinds < INDULGE_MIN_KEPT_KINDS) {
            return false;
        }
        return lastIndulgence == null
                || ChronoUnit.DAYS.between(lastIndulgence, today) >= INDULGE_COOLDOWN_DAYS;
    }

    // ==================== 组装响应 ====================

    public record TodayView(
            String date,
            long assignmentId,
            long cardId,
            String text,
            String type,
            String category,
            int difficulty,
            String indulgenceKind,
            boolean kept,
            boolean canIndulge,
            /** 已揭晓：false = 还是卡背，前端要点一下才翻开 */
            boolean revealed,
            /** 今天已经抽了几次 */
            int drawCount,
            /** 每天最多抽几次；<b>0 = 无限</b>（开发期默认） */
            int maxDraws,
            /** 还能不能再抽一次（没留住 + 配额没用完）。前端据此决定要不要画重抽入口 */
            boolean canRedraw,
            Evidence evidence,
            ScienceNotes.Note science
    ) {
        /** 后端统一算，避免前端自己推配额推错；也保护旧数据（drawCount 缺省按 0 处理） */
        public static boolean redrawable(boolean kept, int drawCount, int maxDraws) {
            return !kept && canDrawAgain(drawCount, maxDraws);
        }
    }

    /** 补留列表里的一条 */
    public record HistoryItem(
            String date,
            long assignmentId,
            long cardId,
            String text,
            String type,
            String category,
            int difficulty,
            boolean kept,
            Evidence evidence,
            ScienceNotes.Note science
    ) {
    }

    private HistoryItem item(Assignment a, Card card) {
        return new HistoryItem(
                a.assignedDate().toString(),
                a.id(),
                card.id(),
                card.text(),
                card.type(),
                card.category(),
                card.difficulty(),
                a.isKept(),
                Evidence.of(card),
                science.get(card.scienceKey()).orElse(null));
    }

    private boolean canIndulge(long userId, LocalDate today) {
        return canIndulge(
                cards.keptKinds(userId),
                assignments.lastIndulgenceDate(userId).orElse(null),
                assignments.wasIndulgence(userId, today.minusDays(1)),
                assignments.findByDate(userId, today).map(Assignment::hasSwapped).orElse(false),
                today);
    }

    private TodayView view(long userId, LocalDate today, Assignment a, Card card, boolean canIndulge) {
        // ★ 留住了就一定是已揭晓：不可能"留住了一张从没翻开过的卡"。
        //   这条护栏是为了防 V3 那次迁移的同类疏漏 —— 若库里出现 KEPT + revealed_at IS NULL，
        //   前端会画出一个没有任何按钮的空白卡背（翻不开也留不了），是个死状态。
        boolean revealed = a.isRevealed() || a.isKept();
        return new TodayView(
                today.toString(),
                a.id(),
                card.id(),
                card.text(),
                card.type(),
                card.category(),
                card.difficulty(),
                card.indulgenceKind(),
                a.isKept(),
                canIndulge,
                revealed,
                a.drawCount(),
                maxDrawsPerDay,
                TodayView.redrawable(a.isKept(), a.drawCount(), maxDrawsPerDay),
                Evidence.of(card),
                science.get(card.scienceKey()).orElse(null));
    }

    private LocalDate todayOf(long userId) {
        return LocalDate.now(ZoneId.of(users.timezone(userId)));
    }
}
