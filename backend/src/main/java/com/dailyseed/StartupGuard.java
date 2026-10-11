package com.dailyseed;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * 开发期配置的"别忘改回去"护栏。
 *
 * <p>目前只有一条，但它是会真出事的一条：{@code dailyseed.draw.max-per-day=0} 表示
 * <b>可以无限重抽</b>——这是开发期为了方便连着抽看手感与分布才开的。
 * 它一旦跟着上线，用户能一直重抽到满意为止，那会直接推翻两件产品设计：
 * 「不确定性的味道」（§3.2）和放纵日门槛的意义（§5.5）。
 *
 * <p>为什么不用"安静地记一行日志"：那种提示没人看。<br>
 * 为什么不用"悄悄把 0 当成 1"：那会让开发期的手动验证莫名失效，而且**改动了用户明确设过的值**，
 * 是更坏的一种意外。
 *
 * <p>所以取中间那条：<b>配置本身照旧生效，但必须显式承认这是开发模式</b>。
 * 上线时只要漏配了承认开关（生产环境当然不会配），应用就**起不来**，
 * 而不是带着一个无限抽卡的口子安静地跑起来。
 */
@Component
public class StartupGuard {

    private static final Logger log = LoggerFactory.getLogger(StartupGuard.class);

    private final int maxDrawsPerDay;
    private final boolean devModeAcknowledged;
    private final boolean cookieEnabled;
    private final boolean cookieSecure;

    public StartupGuard(@Value("${dailyseed.draw.max-per-day:0}") int maxDrawsPerDay,
                        @Value("${dailyseed.dev-mode:false}") boolean devModeAcknowledged,
                        @Value("${dailyseed.session.cookie.enabled:true}") boolean cookieEnabled,
                        @Value("${dailyseed.session.cookie.secure:false}") boolean cookieSecure) {
        this.maxDrawsPerDay = maxDrawsPerDay;
        this.devModeAcknowledged = devModeAcknowledged;
        this.cookieEnabled = cookieEnabled;
        this.cookieSecure = cookieSecure;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void check() {
        // ---- 会拦住启动的那一条 ----
        if (maxDrawsPerDay <= 0 && !devModeAcknowledged) {
            throw new IllegalStateException("""
                    配置有问题，拒绝启动：
                      dailyseed.draw.max-per-day = %d 表示**每天可以无限重抽**，那是开发期才该有的。
                      要跑生产：DAILYSEED_DRAW_MAX_PER_DAY=1
                      确实是开发机：DAILYSEED_DEV_MODE=true
                    （这条护栏就是为"忘了改配置就上线"准备的，见交接简报 §8）"""
                    .formatted(maxDrawsPerDay));
        }

        // ---- 只提醒、不拦的两条：它们是"上线时该确认一次"的部署项 ----
        if (cookieEnabled && !cookieSecure) {
            log.warn("dailyseed.session.cookie.secure=false：Cookie 会在 http 上明文传输。"
                    + "生产环境（https）请设 DAILYSEED_SESSION_COOKIE_SECURE=true");
        }
        if (maxDrawsPerDay <= 0) {
            log.warn("开发模式已确认：抽卡配额 = 0（无限重抽）。上线前必须改回 1");
        }

        log.info("启动检查通过：抽卡配额={}（{}）、身份 Cookie={}（secure={}）",
                maxDrawsPerDay <= 0 ? "无限" : maxDrawsPerDay,
                devModeAcknowledged ? "已确认为开发模式" : "生产语义",
                cookieEnabled ? "开" : "关",
                cookieSecure);
    }
}
