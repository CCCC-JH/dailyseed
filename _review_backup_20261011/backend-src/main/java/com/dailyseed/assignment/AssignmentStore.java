package com.dailyseed.assignment;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** daily_assignments 的读写（MySQL 方言：ON DUPLICATE KEY UPDATE / CURRENT_TIMESTAMP(6)）。 */
@Repository
public class AssignmentStore {

    private static final String SELECT = """
            SELECT id, user_id, card_id, assigned_date, state, revealed_at, draw_count, kept_at, swapped_at
            FROM daily_assignments
            """;

    private static final RowMapper<Assignment> MAPPER = (rs, i) -> new Assignment(
            rs.getLong("id"),
            rs.getLong("user_id"),
            rs.getLong("card_id"),
            rs.getObject("assigned_date", LocalDate.class),
            rs.getString("state"),
            rs.getObject("revealed_at", LocalDateTime.class),
            rs.getInt("draw_count"),
            rs.getObject("kept_at", LocalDateTime.class),
            rs.getObject("swapped_at", LocalDateTime.class));

    private final JdbcClient jdbc;

    public AssignmentStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Assignment> findByDate(long userId, LocalDate date) {
        return jdbc.sql(SELECT + " WHERE user_id = :u AND assigned_date = :d")
                .param("u", userId).param("d", date)
                .query(MAPPER).optional();
    }

    public Optional<Assignment> findById(long assignmentId) {
        return jdbc.sql(SELECT + " WHERE id = :id")
                .param("id", assignmentId)
                .query(MAPPER).optional();
    }

    /** 补留窗口用：某段日期内的发放记录，新的在前 */
    public List<Assignment> findBetween(long userId, LocalDate from, LocalDate to) {
        return jdbc.sql(SELECT + """
                        WHERE user_id = :u AND assigned_date BETWEEN :from AND :to
                        ORDER BY assigned_date DESC
                        """)
                .param("u", userId).param("from", from).param("to", to)
                .query(MAPPER).list();
    }

    /**
     * 这个人的全部发放记录，新的在前（探索记录页用）。
     *
     * <p>刻意**不带天数上限**：探索记录是"我走过的路"，不是补留窗口那种有时效的东西，
     * 砍掉三个月前的记录等于把用户的路抹了。索引走的是 {@code uk_assign_user_date} 的左前缀。
     */
    public List<Assignment> findAll(long userId) {
        return jdbc.sql(SELECT + " WHERE user_id = :u ORDER BY assigned_date DESC")
                .param("u", userId)
                .query(MAPPER).list();
    }

    /**
     * 幂等落库：靠 {@code UNIQUE KEY (user_id, assigned_date)} + {@code ON DUPLICATE KEY UPDATE id = id}（空操作）。
     *
     * <p>不用 {@code INSERT IGNORE}：那会把外键错误之类的真问题一起吞掉。
     * 并发时两个请求可能同时算，但选卡是确定性的（种子 = hash(userId, date)），
     * 所以它们挑的是同一张；谁先落库谁生效，后到的读到同一行。
     */
    public Assignment insertIfAbsent(long userId, long cardId, LocalDate date, int drawCount) {
        jdbc.sql("""
                        INSERT INTO daily_assignments (user_id, card_id, assigned_date, draw_count)
                        VALUES (:u, :c, :d, :n)
                        ON DUPLICATE KEY UPDATE id = id
                        """)
                .param("u", userId).param("c", cardId).param("d", date).param("n", drawCount)
                .update();
        return findByDate(userId, date).orElseThrow(
                () -> new IllegalStateException("每日发放落库后读不到：" + userId + " / " + date));
    }

    /**
     * 揭晓：把这张卡标成"已经翻开给用户看过"。
     *
     * <p>{@code AND revealed_at IS NULL} 让重复揭晓不覆盖时间戳（幂等），
     * 和毕业那套是同一个路子。
     */
    public void markRevealed(long assignmentId) {
        jdbc.sql("""
                        UPDATE daily_assignments
                        SET revealed_at = CURRENT_TIMESTAMP(6)
                        WHERE id = :id AND revealed_at IS NULL
                        """)
                .param("id", assignmentId).update();
    }

    /**
     * 重抽：把当天那一行换成新卡，并 +1 次抽卡计数。
     *
     * <p>不碰 {@code swapped_at}——那是「放纵日换卡」的标记，两者语义不同，混用会让放纵门槛算错。
     *
     * <p>⚠️ <b>{@code WHERE draw_count = :n} 是并发安全的闸门</b>：调用方在决定"这一轮抽到的是哪张卡"
     * 时用的是它读到的那个 {@code draw_count}（它同时是选卡种子的输入），所以这次更新必须携带同一个值。
     * 两个并发重抽会读到同一个 count，于是只有一个能改到行，另一个拿到 0 并去重读重算——
     * 这样既不会出现"两次重抽共用一个种子、抽到同一张"，也不会让 {@code draw_count} 少加
     * （原本无条件自增时，N 个并发重抽只 +1，配额形同不存在）。
     *
     * @return 真的改了 1 行 → true；有人在中间改过这一行 → false（调用方应重读后重试）
     */
    public boolean redraw(long assignmentId, long newCardId, int expectedDrawCount) {
        return jdbc.sql("""
                        UPDATE daily_assignments
                        SET card_id = :c,
                            draw_count = draw_count + 1,
                            revealed_at = CURRENT_TIMESTAMP(6)
                        WHERE id = :id AND draw_count = :n
                        """)
                .param("c", newCardId).param("id", assignmentId).param("n", expectedDrawCount)
                .update() > 0;
    }

    /** 首次抽卡：落库时就算抽过一次，同时标记已揭晓 */
    public void markDrawn(long assignmentId) {
        jdbc.sql("""
                        UPDATE daily_assignments
                        SET draw_count = draw_count + 1,
                            revealed_at = CURRENT_TIMESTAMP(6)
                        WHERE id = :id
                        """)
                .param("id", assignmentId).update();
    }

    /**
     * 把这一行标成「已留住」。
     *
     * <p>⚠️ <b>返回值是并发安全的关键，不要丢掉它</b>：{@code WHERE state <> 'KEPT'} 让这次更新
     * 具备"只有一个请求能改到"的语义（并发的第二个 UPDATE 会被行锁挡住，等第一个提交后条件不再成立），
     * 所以返回 1 的那个请求才是"真正完成这次留住"的请求。
     *
     * @return 真的改了 1 行 → true；这行本来就是 KEPT（被别人抢先、或重复点击）→ false
     */
    public boolean markKept(long assignmentId) {
        return jdbc.sql("""
                        UPDATE daily_assignments
                        SET state = 'KEPT', kept_at = CURRENT_TIMESTAMP(6)
                        WHERE id = :id AND state <> 'KEPT'
                        """)
                .param("id", assignmentId).update() > 0;
    }

    /**
     * 「留着」：花园里 kept_count +1（放纵卡不走这里）。
     *
     * <p>⚠️ <b>必须由 {@link #markKept} 的结果来把关</b>。这里原本是无条件自增，
     * 看起来没问题——Service 里已经先判过 {@code isKept()} 了。但那是个**读检查**：
     * 并发的 8 个请求可以同时读到 PENDING、同时通过检查，然后各加一次，
     * 于是 {@code kept_count} 变成 8。实测过：并发 8 次「留着」拿到 5~7。
     *
     * <p>而 {@code kept_count} 驱动两件产品语义：「毕业小标记 ≥7」（§6.1）和放纵日门槛。
     * 也就是说这个 bug 的效果是——**手抖连点几次就能刷出毕业入口**。
     * 串行测试永远抓不到它（`verify_api.py` 的 A13 是全绿的），只有并发实验能。
     */
    public void addKept(long userId, long cardId) {
        jdbc.sql("""
                        INSERT INTO user_cards (user_id, card_id, kept_count, first_kept_at, last_kept_at)
                        VALUES (:u, :c, 1, CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6))
                        ON DUPLICATE KEY UPDATE
                            kept_count = kept_count + 1,
                            last_kept_at = CURRENT_TIMESTAMP(6)
                        """)
                .param("u", userId).param("c", cardId).update();
    }

    /** 放纵日：把今天换成一张放纵卡（每天最多一次，由 swapped_at 保证） */
    public void swapCard(long assignmentId, long newCardId) {
        jdbc.sql("""
                        UPDATE daily_assignments
                        SET card_id = :c, swapped_at = CURRENT_TIMESTAMP(6)
                        WHERE id = :id
                        """)
                .param("c", newCardId).param("id", assignmentId).update();
    }

    /** 上次放纵是哪天（冷却用） */
    public Optional<LocalDate> lastIndulgenceDate(long userId) {
        List<LocalDate> rows = jdbc.sql("""
                        SELECT MAX(a.assigned_date)
                        FROM daily_assignments a
                        JOIN cards c ON c.id = a.card_id
                        WHERE a.user_id = :u AND c.type = 'INDULGE'
                        """)
                .param("u", userId)
                .query((rs, i) -> rs.getObject(1, LocalDate.class))
                .list();
        return rows.isEmpty() || rows.get(0) == null ? Optional.empty() : Optional.of(rows.get(0));
    }

    public boolean wasIndulgence(long userId, LocalDate date) {
        Boolean exists = jdbc.sql("""
                        SELECT EXISTS (
                            SELECT 1 FROM daily_assignments a
                            JOIN cards c ON c.id = a.card_id
                            WHERE a.user_id = :u AND a.assigned_date = :d AND c.type = 'INDULGE'
                        )
                        """)
                .param("u", userId).param("d", date)
                .query(Boolean.class).single();
        return Boolean.TRUE.equals(exists);
    }
}
