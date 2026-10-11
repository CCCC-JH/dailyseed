package com.dailyseed.user;

import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class RecoveryTokenStore {
    private final JdbcClient jdbc;
    private final SecureRandom random = new SecureRandom();

    public RecoveryTokenStore(JdbcClient jdbc) { this.jdbc = jdbc; }

    public Optional<Long> findUserId(String token) {
        if (token == null || !token.matches("[a-f0-9]{64}")) return Optional.empty();
        return jdbc.sql("SELECT user_id FROM recovery_tokens WHERE token_hash = :hash AND expires_at > CURRENT_TIMESTAMP(6)")
                .param("hash", UserStore.sha256(token)).query(Long.class).optional();
    }

    @Transactional
    public String issue(long userId) {
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        String token = HexFormat.of().formatHex(bytes);
        jdbc.sql("DELETE FROM recovery_tokens WHERE user_id = :u AND expires_at <= CURRENT_TIMESTAMP(6)")
                .param("u", userId).update();
        jdbc.sql("INSERT INTO recovery_tokens (token_hash, user_id, expires_at) VALUES (:hash, :u, DATE_ADD(CURRENT_TIMESTAMP(6), INTERVAL 400 DAY))")
                .param("hash", UserStore.sha256(token)).param("u", userId).update();
        return token;
    }

    public void renew(String token) {
        jdbc.sql("UPDATE recovery_tokens SET expires_at = DATE_ADD(CURRENT_TIMESTAMP(6), INTERVAL 400 DAY) WHERE token_hash = :hash AND expires_at > CURRENT_TIMESTAMP(6)")
                .param("hash", UserStore.sha256(token)).update();
    }
}
