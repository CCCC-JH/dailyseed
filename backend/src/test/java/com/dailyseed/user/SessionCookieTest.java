package com.dailyseed.user;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;

class SessionCookieTest {
    static class Tokens extends RecoveryTokenStore {
        final Map<String, Long> known = new HashMap<>();
        int issued;
        int renewed;
        Tokens() { super(null); }
        @Override public Optional<Long> findUserId(String token) { return Optional.ofNullable(known.get(token)); }
        @Override public String issue(long userId) {
            String token = String.format("%064x", ++issued);
            known.put(token, userId);
            return token;
        }
        @Override public void renew(String token) { renewed++; }
    }
    private MockHttpServletRequest request(String value) {
        var request = new MockHttpServletRequest();
        request.setCookies(new Cookie(SessionCookie.NAME, value));
        return request;
    }
    @Test void rejectsNumericAndForgedCookies() {
        var tokens = new Tokens();
        var cookie = new SessionCookie(tokens, true, false);
        assertThat(cookie.readUserId(request("42"))).isEmpty();
        assertThat(cookie.readUserId(request("a".repeat(64)))).isEmpty();
        assertThat(cookie.readUserId(request("garbage"))).isEmpty();
        assertThat(cookie.readUserId(new MockHttpServletRequest())).isEmpty();
    }
    @Test void resolvesOnlyStoredTokenAndRejectsRevokedToken() {
        var tokens = new Tokens();
        var cookie = new SessionCookie(tokens, true, false);
        String token = tokens.issue(42);
        assertThat(cookie.readUserId(request(token))).contains(42L);
        tokens.known.clear();
        assertThat(cookie.readUserId(request(token))).isEmpty();
    }
    @Test void remembersWithCookieProtectionsAndReusesExistingToken() {
        var tokens = new Tokens();
        var cookie = new SessionCookie(tokens, true, true);
        String token = tokens.issue(42);
        var headers = new HttpHeaders();
        cookie.remember(headers, 42, request(token));
        assertThat(tokens.issued).isEqualTo(1);
        assertThat(tokens.renewed).isEqualTo(1);
        assertThat(headers.getFirst(HttpHeaders.SET_COOKIE)).contains(token, "HttpOnly", "Secure", "SameSite=Lax", "Path=/");
    }
    @Test void changingAccountIssuesDifferentCredential() {
        var tokens = new Tokens();
        var cookie = new SessionCookie(tokens, true, false);
        String old = tokens.issue(42);
        var headers = new HttpHeaders();
        cookie.remember(headers, 99, request(old));
        assertThat(tokens.issued).isEqualTo(2);
        assertThat(headers.getFirst(HttpHeaders.SET_COOKIE)).doesNotContain(old);
    }
    @Test void disabledCookieNeitherReadsNorWrites() {
        var tokens = new Tokens();
        var cookie = new SessionCookie(tokens, false, false);
        var headers = new HttpHeaders();
        cookie.remember(headers, 42, new MockHttpServletRequest());
        assertThat(headers).isEmpty();
        assertThat(tokens.issued).isZero();
        assertThat(cookie.readUserId(request(tokens.issue(42)))).isEmpty();
    }
}
