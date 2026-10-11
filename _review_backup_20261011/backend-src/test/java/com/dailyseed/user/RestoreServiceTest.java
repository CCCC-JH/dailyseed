package com.dailyseed.user;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** 同步码的整理规则（纯函数，不连数据库）。 */
class RestoreServiceTest {

    @Test
    @DisplayName("★ 规范形态必须是【带连字符】的 K7M2-P9QX——库里哈希的就是这一串")
    void canonicalFormKeepsTheDash() {
        assertThat(RestoreService.canonicalSyncCode("K7M2-P9QX")).isEqualTo("K7M2-P9QX");
        assertThat(RestoreService.canonicalSyncCode("K7M2P9QX")).isEqualTo("K7M2-P9QX");
        // 长度断言是次要的，形态断言才是这条测试的重点：
        // 曾经这里的实现把连字符抹掉去查，于是"码明明对着，恢复却永远说没有这个码"
        assertThat(RestoreService.canonicalSyncCode("K7M2P9QX")).contains("-");
        assertThat(RestoreService.canonicalSyncCode("K7M2P9QX")).hasSize(9);
    }

    @Test
    @DisplayName("用户抄回来的各种写法都被认成同一串码：分组/小写/空格/全角空格/重复连字符")
    void normalizesWhatHumansActuallyType() {
        assertThat(RestoreService.canonicalSyncCode("k7m2p9qx")).isEqualTo("K7M2-P9QX");
        assertThat(RestoreService.canonicalSyncCode("K7M2 P9QX")).isEqualTo("K7M2-P9QX");
        assertThat(RestoreService.canonicalSyncCode(" K7M2P9QX ")).isEqualTo("K7M2-P9QX");
        assertThat(RestoreService.canonicalSyncCode("K7M2\u3000P9QX")).isEqualTo("K7M2-P9QX");
        assertThat(RestoreService.canonicalSyncCode("K7M2--P9QX")).isEqualTo("K7M2-P9QX");
    }

    @Test
    @DisplayName("只整理、不猜：有效字符不是正好 8 个就一律不接受（猜出来的码等于放宽凭据强度）")
    void doesNotGuess() {
        assertThat(RestoreService.canonicalSyncCode("K7M2P9Q")).isEmpty();
        assertThat(RestoreService.canonicalSyncCode("K7M2P9QX3")).isEmpty();
        assertThat(RestoreService.canonicalSyncCode(null)).isEmpty();
        assertThat(RestoreService.canonicalSyncCode("")).isEmpty();
        assertThat(RestoreService.canonicalSyncCode("   ")).isEmpty();
        assertThat(RestoreService.canonicalSyncCode("K7M2-P9Q!")).isEmpty(); // 多打了一个标点也算多
    }

    @Test
    @DisplayName("★ 全角空格必须被剥掉——用 [^0-9A-Za-z] 那种写法时它会被当成「字母数字」躲过去")
    void fullWidthSpaceIsNotMistakenForALetter() {
        // 中文输入法下打空格很容易出全角，它和半角空格必须一样被忽略
        assertThat(RestoreService.bareSyncCode("K7M2\u3000P9QX")).isEqualTo("K7M2P9QX");
        assertThat(RestoreService.bareSyncCode("K7M2\u3000P9QX")).hasSize(8);
        assertThat(RestoreService.canonicalSyncCode("K7M2\u3000P9QX")).isEqualTo("K7M2-P9QX");
    }

    @Test
    @DisplayName("裸码与展示形态：给前端/日志看的分组写法")
    void bareAndDisplayForms() {
        assertThat(RestoreService.bareSyncCode("k7m2-p9qx")).isEqualTo("K7M2P9QX");
        assertThat(RestoreService.displaySyncCode("k7m2p9qx")).isEqualTo("K7M2-P9QX");
        // 长度不够时不该硬塞一个连字符进去
        assertThat(RestoreService.displaySyncCode("K7")).isEqualTo("K7");
        assertThat(RestoreService.displaySyncCode(null)).isEmpty();
    }
}
