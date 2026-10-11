package com.dailyseed.card;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** 卡片与「我的花园」的只读查询。 */
@Repository
public class CardStore {

    private static final String SELECT_CARD = """
            SELECT c.id, c.type, c.category, c.`text`, c.difficulty, c.photo_hint, c.shareable,
                   c.indulgence_kind, c.why, c.evidence, c.evidence_level, c.science_key
            FROM cards c
            """;

    private static final RowMapper<Card> MAPPER = (ResultSet rs, int rowNum) -> new Card(
            rs.getLong("id"),
            rs.getString("type"),
            rs.getString("category"),
            rs.getString("text"),
            rs.getInt("difficulty"),
            rs.getBoolean("photo_hint"),
            rs.getBoolean("shareable"),
            rs.getString("indulgence_kind"),
            rs.getString("why"),
            rs.getString("evidence"),
            rs.getString("evidence_level"),
            rs.getString("science_key"));

    private final JdbcClient jdbc;

    public CardStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public List<Card> activeCards() {
        return jdbc.sql(SELECT_CARD + " WHERE c.status = 'ACTIVE'").query(MAPPER).list();
    }

    public Optional<Card> findById(long cardId) {
        return jdbc.sql(SELECT_CARD + " WHERE c.id = :id").param("id", cardId).query(MAPPER).optional();
    }

    /** 某天发给某人的那张卡（用于「不连续同类 / 尽量交替类型」） */
    public Optional<Card> cardOfDate(long userId, LocalDate date) {
        return jdbc.sql(SELECT_CARD + """
                        JOIN daily_assignments a ON a.card_id = c.id
                        WHERE a.user_id = :u AND a.assigned_date = :d
                        """)
                .param("u", userId).param("d", date)
                .query(MAPPER).optional();
    }

    /** 硬约束用：since 之后已经发过的卡 */
    public Set<Long> assignedCardIdsSince(long userId, LocalDate since) {
        return new HashSet<>(jdbc.sql("""
                        SELECT card_id FROM daily_assignments
                        WHERE user_id = :u AND assigned_date >= :since
                        """)
                .param("u", userId).param("since", since)
                .query(Long.class).list());
    }

    /** 每张卡最近一次发放的日期（软权重「太久没见」用；一次查询，别放进循环） */
    public Map<Long, LocalDate> lastAssignedDates(long userId, LocalDate since) {
        List<Map.Entry<Long, LocalDate>> rows = jdbc.sql("""
                        SELECT card_id, MAX(assigned_date) AS last_date
                        FROM daily_assignments
                        WHERE user_id = :u AND assigned_date >= :since
                        GROUP BY card_id
                        """)
                .param("u", userId).param("since", since)
                .query((rs, i) -> Map.entry(rs.getLong("card_id"), rs.getObject("last_date", LocalDate.class)))
                .list();
        Map<Long, LocalDate> last = new HashMap<>();
        rows.forEach(e -> last.put(e.getKey(), e.getValue()));
        return last;
    }

    /** 留着次数（驱动抽卡权重；放纵卡不进这张表） */
    public Map<Long, Integer> keptCounts(long userId) {
        List<Map.Entry<Long, Integer>> rows = jdbc.sql(
                        "SELECT card_id, kept_count FROM user_cards WHERE user_id = :u")
                .param("u", userId)
                .query((rs, i) -> Map.entry(rs.getLong("card_id"), rs.getInt("kept_count")))
                .list();
        Map<Long, Integer> counts = new HashMap<>();
        rows.forEach(e -> counts.put(e.getKey(), e.getValue()));
        return counts;
    }

    /** 「累计留住过 N 种」——放纵日的门槛用它（累计，永不归零） */
    public int keptKinds(long userId) {
        Integer n = jdbc.sql("""
                        SELECT COUNT(*) FROM user_cards
                        WHERE user_id = :u AND kept_count > 0
                        """)
                .param("u", userId).query(Integer.class).single();
        return n == null ? 0 : n;
    }

    public Set<Long> graduatedCardIds(long userId) {
        return new HashSet<>(jdbc.sql("""
                        SELECT card_id FROM user_cards
                        WHERE user_id = :u AND state = 'GRADUATED'
                        """)
                .param("u", userId).query(Long.class).list());
    }
}
