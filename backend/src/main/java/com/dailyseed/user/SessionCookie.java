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
 * HttpOnly Cookie 保存 256 位随机恢复令牌；数据库只保存哈希与到期时间。
 * 不接受旧版数字 userId Cookie。有效本地设备登录后会自动签发新令牌。
 * Cookie 是身份凭据，HttpOnly / SameSite 只是附加保护，不能替代服务端校验。
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

    private final RecoveryTokenStore tokens;
    private final boolean enabled;
    private final boolean secure;

    public SessionCookie(RecoveryTokenStore tokens,
                         @Value("${dailyseed.session.cookie.enabled:true}") boolean enabled,
                         @Value("${dailyseed.session.cookie.secure:false}") boolean secure) {
        this.tokens = tokens;
        this.enabled = enabled;
        this.secure = secure;
    }

    /** 校验令牌后读回 userId；缺失、伪造、过期都当作没有凭据。 */
    public Optional<Long> readUserId(HttpServletRequest request) {
        if (!enabled || request.getCookies() == null) {
            return Optional.empty();
        }
        return readToken(request).flatMap(tokens::findUserId);
    }

    private Optional<String> readToken(HttpServletRequest request) {
        if (request == null || request.getCookies() == null) return Optional.empty();
        return Arrays.stream(request.getCookies())
                .filter(c -> NAME.equals(c.getName()))
                .map(Cookie::getValue)
                .findFirst()
                .filter(value -> value.matches("[a-f0-9]{64}"));
    }

    /** 「记住这个人」。写进响应头，由浏览器保管。 */
    public void remember(HttpHeaders headers, long userId, HttpServletRequest request) {
        if (!enabled) {
            return;
        }
        Optional<String> current = readToken(request)
                .filter(token -> tokens.findUserId(token).filter(id -> id == userId).isPresent());
        String token;
        if (current.isPresent()) {
            token = current.get();
            tokens.renew(token);
        } else {
            token = tokens.issue(userId);
        }
        headers.add(HttpHeaders.SET_COOKIE, cookie(token, MAX_AGE).toString());
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

}
