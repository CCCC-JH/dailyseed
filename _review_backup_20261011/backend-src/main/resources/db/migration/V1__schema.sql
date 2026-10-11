-- ============================================================
-- DailySeed 表结构（MySQL 8 / InnoDB / utf8mb4）
-- 设计文档 §9 + 卡片库「转换成开发数据」
-- 迁移文件不要手改历史：V1 建表，V2 是生成的卡片种子
-- ============================================================

-- ============ 卡片库 ============
CREATE TABLE cards (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    type            VARCHAR(16)  NOT NULL,          -- HABIT / EXPLORE / INDULGE
    category        VARCHAR(32)  NOT NULL,          -- 8 类之一
    `text`          VARCHAR(64)  NOT NULL,
    occasion        VARCHAR(32)  NULL,
    action          VARCHAR(32)  NULL,
    constraint_key  VARCHAR(32)  NULL,
    difficulty      SMALLINT     NOT NULL DEFAULT 1, -- 0=放纵（零消耗） 1/2/3
    photo_hint      BOOLEAN      NOT NULL DEFAULT FALSE,
    shareable       BOOLEAN      NOT NULL DEFAULT FALSE,
    indulgence_kind VARCHAR(8)   NULL,               -- STOP / GIVE；非放纵卡为 NULL
    why             TEXT         NULL,               -- 内部：为什么有效（质量守门）
    evidence        TEXT         NULL,               -- 展示给用户的依据；NULL = 不显示「?」
    evidence_level  CHAR(1)      NULL,               -- A 研究 / B 机制 / C 无依据
    science_key     VARCHAR(32)  NULL,               -- 指向 science-notes.json
    status          VARCHAR(16)  NOT NULL DEFAULT 'ACTIVE',
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_cards_type (type)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============ 用户（零注册） ============
CREATE TABLE users (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    sync_code_hash  VARCHAR(64)  NOT NULL,           -- 只存哈希
    timezone        VARCHAR(64)  NOT NULL DEFAULT 'Asia/Shanghai',
    remind_at       TIME         NULL,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_sync_code (sync_code_hash)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE user_devices (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    user_id         BIGINT       NOT NULL,
    device_id       VARCHAR(64)  NOT NULL,           -- 本地生成的匿名 ID
    last_seen_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_devices_device (device_id),
    KEY idx_devices_user (user_id),
    CONSTRAINT fk_devices_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============ 每日发放（幂等核心） ============
CREATE TABLE daily_assignments (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    user_id         BIGINT       NOT NULL,
    card_id         BIGINT       NOT NULL,
    assigned_date   DATE         NOT NULL,
    state           VARCHAR(16)  NOT NULL DEFAULT 'PENDING',  -- PENDING/KEPT/DISCARDED
    kept_at         DATETIME(6)  NULL,
    photo_url       TEXT         NULL,
    note            VARCHAR(200) NULL,
    swapped_at      DATETIME(6)  NULL,               -- 非空 = 今天已用过「放纵」入口
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_assign_user_date (user_id, assigned_date),  -- ★ 幂等保证
    CONSTRAINT fk_assign_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_assign_card FOREIGN KEY (card_id) REFERENCES cards (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============ 我的花园 ============
CREATE TABLE user_cards (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    user_id         BIGINT       NOT NULL,
    card_id         BIGINT       NOT NULL,
    kept_count      INT          NOT NULL DEFAULT 0, -- ★ 核心指标
    first_kept_at   DATETIME(6)  NULL,
    last_kept_at    DATETIME(6)  NULL,
    state           VARCHAR(16)  NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE/GRADUATED
    graduated_at    DATETIME(6)  NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_cards (user_id, card_id),
    CONSTRAINT fk_user_cards_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_user_cards_card FOREIGN KEY (card_id) REFERENCES cards (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
