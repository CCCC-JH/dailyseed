package com.dailyseed.user;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.util.Arrays;
import java.util.Optional;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

/**
 * 身份的第二条命：把 userId 种进一个 **HttpOnly Cookie**。
 *
 * <p>为什么要有它（§6.4 那个"物理上无法送达"的死角）：身份只认 {@code X-Device-Id}，
 * 而它存在 localStorage 里。用户一清浏览器缓存，localStorage **和**同步码一起消失——
 * 后端认不出他是谁，任何"服务端保管、以后补发"的方案都送不到。
 * Cookie 是另一套存储：清"网站数据"会一起清掉，但**只清 localStorage / 换个浏览器 profile**
 * 这类最常见的丢法，它还在。这不是万无一失，是把概率从"很容易丢"降到"要丢一起丢"。
 *
 * <p>三条刻意的取舍：
 * <ol>
 *   <li><b>HttpOnly</b>：脚本读不到它，XSS 偷不走。代价是前端**看不见**自己的 userId，
 *       所以"是不是靠 Cookie 认出我"只能由后端在响应里表达，不能由前端判断</li>
 *   <li><b>不放任何秘密</b>：里面只有一个自增数字，不是同步码、不是哈希。
 *       拿着它**不能**像同步码那样在别处恢复——同步码仍然是唯一的凭据</li>
 *   <li><b>可关</b>：{@code dailyseed.session.cookie.enabled=false} 就完全退回只管 localStorage。
 *       它是一条持久标识符，介意隐私的部署有权不要它</li>
 * </ol>
 */
@Component
public class SessionCookie {

    /** 名字带 dailyseed 前缀，同一台机器上跑多个项目时不打架 */
    static final String NAME = "dailyseed_uid";

    /**
     * 400 天——Chrome 对 Set-Cookie 的 Max-Age 上限就是 400 天（超过会被截断到 400 天）。
     * 这是"越久越好"的场景：它只是一条回家的路，没有过期就到期一说。
     */
    private static final Duration MAX_AGE = Duration.ofDays(400);

    private final boolean enabled;
    private final boolean secure;

    public SessionCookie(@Value("${dailyseed.session.cookie.enabled:true}") boolean enabled,
                         @Value("${dailyseed.session.cookie.secure:false}") boolean secure) {
        this.enabled = enabled;
        this.secure = secure;
    }

    /** 读回 userId。没开、没有、或者值不是数字，都当作"没有"。 */
    public Optional<Long> readUserId(HttpServletRequest request) {
        if (!enabled || request.getCookies() == null) {
            return Optional.empty();
        }
        return Arrays.stream(request.getCookies())
                .filter(c -> NAME.equals(c.getName()))
                .map(Cookie::getValue)
                .findFirst()
                .flatMap(SessionCookie::parseUserId);
    }

    /** 「记住这个人」。写进响应头，由浏览器保管。 */
    public void remember(HttpHeaders headers, long userId) {
        if (!enabled) {
            return;
        }
        headers.add(HttpHeaders.SET_COOKIE, cookie(String.valueOf(userId), MAX_AGE).toString());
    }

    /** 这个数值是坏的（比如手改过）：清掉它，免得每次请求都白读一遍并走进自愈 */
    public void forget(HttpHeaders headers) {
        if (!enabled) {
            return;
        }
        headers.add(HttpHeaders.SET_COOKIE, cookie("", Duration.ZERO).toString());
    }

    private ResponseCookie cookie(String value, Duration maxAge) {
        return ResponseCookie.from(NAME, value)
                .httpOnly(true)
                .secure(secure)
                // Lax：同站导航会带上、跨站 POST 不会。身份接口要防 CSRF，但也要能从
                // 地址栏直接打开页面时被带上，Lax 正好。
                .sameSite("Lax")
                .path("/")
                .maxAge(maxAge)
                .build();
    }

    static Optional<Long> parseUserId(String raw) {
        try {
            long userId = Long.parseLong(raw.trim());
            return userId > 0 ? Optional.of(userId) : Optional.empty();
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
