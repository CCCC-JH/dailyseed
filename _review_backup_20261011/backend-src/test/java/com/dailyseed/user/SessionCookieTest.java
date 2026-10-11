package com.dailyseed.user;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Cookie 里那个 userId 的解析（纯函数，不连数据库）。
 *
 * <p>包一层解析而不是直接 {@code Long.parseLong}，是因为这个值**用户能改**：
 * 手写一个非数字进去不该让整个接口 500，而应该被当成"没有凭据"、走正常建号流程。
 */
class SessionCookieTest {

    @Test
    @DisplayName("正常值能读出来")
    void readsPositiveIds() {
        assertThat(SessionCookie.parseUserId("42")).contains(42L);
        assertThat(SessionCookie.parseUserId(" 42 ")).contains(42L);
    }

    @Test
    @DisplayName("0 / 负数 / 非数字 / 空白 → 都当作没有凭据（不能让手改的值把接口打崩）")
    void rejectsGarbage() {
        assertThat(SessionCookie.parseUserId("0")).isEmpty();
        assertThat(SessionCookie.parseUserId("-1")).isEmpty();
        assertThat(SessionCookie.parseUserId("abc")).isEmpty();
        assertThat(SessionCookie.parseUserId("1e3")).isEmpty();
        assertThat(SessionCookie.parseUserId("")).isEmpty();
        assertThat(SessionCookie.parseUserId("  ")).isEmpty();
    }

    @Test
    @DisplayName("Cookie 名带 dailyseed 前缀：同一台机器上跑多个项目时不打架")
    void cookieNameIsNamespaced() {
        assertThat(SessionCookie.NAME).startsWith("dailyseed");
    }

    @Test
    @DisplayName("Optional.empty 而不是抛异常——调用方只关心「有没有」")
    void neverThrows() {
        assertThat(SessionCookie.parseUserId("9999999999999999999999")).isInstanceOf(Optional.class);
    }
}
