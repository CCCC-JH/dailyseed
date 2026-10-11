-- Cookie 是身份凭据，不能直接信任可枚举的用户编号。
-- 原始随机令牌只放在浏览器，数据库仅存 SHA-256 哈希。
CREATE TABLE recovery_tokens (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id BIGINT NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    PRIMARY KEY (token_hash),
    KEY idx_recovery_user (user_id),
    KEY idx_recovery_expiry (expires_at),
    CONSTRAINT fk_recovery_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
