package com.dailyseed.explored;

import static org.assertj.core.api.Assertions.assertThat;

import com.dailyseed.assignment.Assignment;
import com.dailyseed.assignment.AssignmentStore;
import com.dailyseed.card.Card;
import com.dailyseed.card.CardStore;
import com.dailyseed.card.ScienceNotes;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Collection;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 探索记录的纯函数测试——不连数据库。
 *
 * <p>「只有探索卡进这一页」这条线**刻意由这里的纯函数守着**，而不是靠 SQL 的 WHERE：
 * 纯函数改了会红，SQL 改了没人知道。花园那边守放纵卡用的是同一个套路。
 */
class ExploredServiceTest {

    private static Assignment a(long cardId, String date, String state) {
        return Assignment.of(1, cardId, LocalDate.parse(date), state);
    }

    @Test
    @DisplayName("★ 只有探索卡进这一页——放纵卡、习惯卡一张都不许漏进来（§3.2 各进各的家 / 红线 5）")
    void onlyExploreCardsAreVisible() {
        assertThat(ExploredService.visibleInExplored(Card.EXPLORE)).isTrue();
        assertThat(ExploredService.visibleInExplored(Card.INDULGE)).isFalse();
        assertThat(ExploredService.visibleInExplored(Card.HABIT)).isFalse();
    }

    @Test
    @DisplayName("同一张卡只留最后一次遇见它的记录（重抽会让同一张卡出现在不同日子）")
    void sameCardAppearsOnce() {
        Map<Long, Assignment> deduped = ExploredService.dedupeByCard(List.of(
                a(33, "2026-10-08", "KEPT"),
                a(33, "2026-09-01", "PENDING"),
                a(55, "2026-09-20", "PENDING")));

        assertThat(deduped).hasSize(2);
        assertThat(deduped.get(33L).assignedDate()).isEqualTo(LocalDate.parse("2026-10-08"));
    }

    @Test
    @DisplayName("顺序不重排：进来是新的在前，出去还是新的在前（前端不用再排一次）")
    void orderIsPreserved() {
        Map<Long, Assignment> deduped = ExploredService.dedupeByCard(List.of(
                a(11, "2026-10-08", "PENDING"),
                a(33, "2026-09-30", "KEPT"),
                a(55, "2026-09-20", "PENDING")));

        assertThat(deduped.keySet()).containsExactly(11L, 33L, 55L);
    }

    @Test
    @DisplayName("空历史不炸：一次都没走过时就是空的")
    void emptyHistoryIsFine() {
        assertThat(ExploredService.dedupeByCard(List.of())).isEmpty();
    }

    @Test
    void batchesCardsAndPreservesLatestExplorations() {
        var history = new AssignmentStore(null) {
            @Override public List<Assignment> findAll(long userId) {
                return List.of(a(11, "2026-10-11", "KEPT"), a(12, "2026-10-10", "PENDING"),
                        a(33, "2026-10-09", "PENDING"), a(99, "2026-10-08", "PENDING"),
                        a(11, "2026-10-01", "PENDING"));
            }
        };
        var batches = new AtomicInteger();
        var catalog = new CardStore(null) {
            @Override public Map<Long, Card> findByIds(Collection<Long> ids) {
                batches.incrementAndGet();
                assertThat(ids).containsExactly(11L, 12L, 33L, 99L);
                return Map.of(11L, card(11, Card.EXPLORE), 12L, card(12, Card.HABIT),
                        33L, card(33, Card.EXPLORE));
            }
            @Override public Optional<Card> findById(long cardId) {
                throw new AssertionError("列表不应再逐张查询");
            }
        };
        var result = new ExploredService(history, catalog, new ScienceNotes(new ObjectMapper())).explored(1);
        assertThat(batches.get()).isEqualTo(1);
        assertThat(result.items()).extracting(ExploredCard::cardId).containsExactly(11L, 33L);
        assertThat(result.items().getFirst().kept()).isTrue();
        assertThat(result.from()).isEqualTo("2026-10-09");
        assertThat(result.to()).isEqualTo("2026-10-11");
    }

    @Test void emptyBatchDoesNotRequireADatabase() {
        assertThat(new CardStore(null).findByIds(List.of())).isEmpty();
    }

    private static Card card(long id, String type) {
        return new Card(id, type, "观察", "一件小事", 1, false, false, null, null, null, null, null);
    }
}
