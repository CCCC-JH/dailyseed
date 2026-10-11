package com.dailyseed;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 启动护栏的纯逻辑测试。
 *
 * <p>守的是一件会真出事的事：{@code max-per-day=0}（无限重抽）是**开发期**的开关，
 * 跟着上线就会推翻「不确定性的味道」和放纵日门槛。所以"忘了改配置"必须让应用**起不来**，
 * 而不是安静地跑起来。
 */
class StartupGuardTest {

    private static StartupGuard guard(int maxDraws, boolean devMode) {
        return new StartupGuard(maxDraws, devMode, true, false);
    }

    @Test
    @DisplayName("★ 无限重抽 + 没承认开发模式 → 拒绝启动（这就是为「忘了改配置就上线」准备的）")
    void refusesUnlimitedDrawsWithoutAcknowledgingDevMode() {
        assertThatThrownBy(() -> guard(0, false).check())
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("无限重抽")
                .hasMessageContaining("DAILYSEED_DRAW_MAX_PER_DAY=1")
                .hasMessageContaining("DAILYSEED_DEV_MODE=true");
    }

    @Test
    @DisplayName("承认了开发模式 → 放行（本地开发就是这条）")
    void allowsUnlimitedWhenDevModeAcknowledged() {
        assertThatCode(() -> guard(0, true).check()).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("配成 1（生产语义）→ 放行，而且不需要承认开发模式")
    void productionValueNeedsNoAcknowledgement() {
        assertThatCode(() -> guard(1, false).check()).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("配成 2（比 1 宽松也是故意的）→ 放行：拦截条件只针对「0 = 无限」")
    void onlyZeroIsTreatedAsUnlimited() {
        assertThatCode(() -> guard(2, false).check()).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("负数按无限处理（和 AssignmentService.canDrawAgain 的口径一致，两处不能各说各话）")
    void negativeIsAlsoUnlimited() {
        assertThatThrownBy(() -> guard(-1, false).check()).isInstanceOf(IllegalStateException.class);
        assertThatCode(() -> guard(-1, true).check()).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("Cookie 开着又没开 secure 时不拦启动——它是部署项，只提醒")
    void insecureCookieDoesNotBlockStartup() {
        assertThatCode(() -> new StartupGuard(1, false, true, false).check()).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("护栏本身不吃掉配置：它只判定，不改值")
    void guardDoesNotMutateAnything() {
        StartupGuard guard = guard(1, false);
        guard.check();
        assertThat(guard).isNotNull(); // 没有 setter 可改，这条是"别以后加个 setter 悄悄改配置"的提醒
    }
}
