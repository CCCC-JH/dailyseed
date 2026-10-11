package com.dailyseed.garden;

import com.dailyseed.card.Evidence;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * {@code user_cards × cards} 的读写：花园（窗台）与已内化清单。
 *
 * <p>「放纵卡不进花园」这条红线**故意不写在 SQL 里**——它由 {@link GardenService#visibleInGarden} 判定，
 * 那样才是一个可单测的纯函数，而不是一句容易被人顺手改掉的 WHERE。
 */
@Repository
public class GardenStore {

    /**
     * 花园里的一行：只取花园要用的列（{@code why} / {@code photo_hint} 这些内部列不取出来）。
     *
     * @param state ACTIVE（还在窗台上）/ GRADUATED（已内化）
     */
    public record GardenRow(
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
            String evidence,
            String evidenceLevel,
            String scienceKey
    ) {

        /** 「?」四段；C 级（没依据）返回 null */
        public Evidence evidenceOrNull() {
            return Evidence.of(evidence, evidenceLevel);
        }
    }

    private static final String SELECT = """
            SELECT uc.card_id, uc.kept_count, uc.first_kept_at, uc.last_kept_at,
                   uc.state, uc.graduated_at,
                   c.type, c.category, c.`text`, c.difficulty,
                   c.evidence, c.evidence_level, c.science_key
            FROM user_cards uc
            JOIN cards c ON c.id = uc.card_id
            """;

    private static final RowMapper<GardenRow> MAPPER = (rs, i) -> new GardenRow(
            rs.getLong("card_id"),
            rs.getString("type"),
            rs.getString("category"),
            rs.getString("text"),
            rs.getInt("difficulty"),
            rs.getInt("kept_count"),
            rs.getObject("first_kept_at", LocalDateTime.class),
            rs.getObject("last_kept_at", LocalDateTime.class),
            rs.getString("state"),
            rs.getObject("graduated_at", LocalDateTime.class),
            rs.getString("evidence"),
            rs.getString("evidence_level"),
            rs.getString("science_key"));

    private final JdbcClient jdbc;

    public GardenStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** 这个用户留过的所有卡（含已毕业、含探索卡）——花园里摆哪些由 Service 判 */
    public List<GardenRow> rows(long userId) {
        return jdbc.sql(SELECT + " WHERE uc.user_id = :u").param("u", userId).query(MAPPER).list();
    }

    /** 只找「留过的」那一张：没留过的卡没有这一行，所以毕业入口天然打不开 */
    public Optional<GardenRow> find(long userId, long cardId) {
        return jdbc.sql(SELECT + " WHERE uc.user_id = :u AND uc.card_id = :c")
                .param("u", userId).param("c", cardId)
                .query(MAPPER).optional();
    }

    /**
     * 宣布毕业：写时间。
     *
     * <p>{@code AND state <> 'GRADUATED'} 是第二道幂等闸——重复宣布不会覆盖第一次的毕业时间。
     * 第一道在 {@link GardenService#shouldStampGraduation}（可单测），两道都留着：
     * 这里防的是并发，那里防的是逻辑写错。
     */
    public void markGraduated(long userId, long cardId) {
        jdbc.sql("""
                        UPDATE user_cards
                        SET state = 'GRADUATED', graduated_at = CURRENT_TIMESTAMP(6)
                        WHERE user_id = :u AND card_id = :c AND state <> 'GRADUATED'
                        """)
                .param("u", userId).param("c", cardId).update();
    }
}
