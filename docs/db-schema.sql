CREATE TABLE `cards` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `type` varchar(16) NOT NULL,
  `category` varchar(32) NOT NULL,
  `text` varchar(64) NOT NULL,
  `occasion` varchar(32) DEFAULT NULL,
  `action` varchar(32) DEFAULT NULL,
  `constraint_key` varchar(32) DEFAULT NULL,
  `difficulty` smallint NOT NULL DEFAULT '1',
  `photo_hint` tinyint(1) NOT NULL DEFAULT '0',
  `shareable` tinyint(1) NOT NULL DEFAULT '0',
  `indulgence_kind` varchar(8) DEFAULT NULL,
  `why` text,
  `evidence` text,
  `evidence_level` char(1) DEFAULT NULL,
  `science_key` varchar(32) DEFAULT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_cards_type` (`type`)
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `daily_assignments` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `card_id` bigint NOT NULL,
  `assigned_date` date NOT NULL,
  `state` varchar(16) NOT NULL DEFAULT 'PENDING',
  `kept_at` datetime(6) DEFAULT NULL,
  `photo_url` text,
  `note` varchar(200) DEFAULT NULL,
  `swapped_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_assign_user_date` (`user_id`,`assigned_date`),
  KEY `fk_assign_card` (`card_id`),
  CONSTRAINT `fk_assign_card` FOREIGN KEY (`card_id`) REFERENCES `cards` (`id`),
  CONSTRAINT `fk_assign_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `flyway_schema_history` (
  `installed_rank` int NOT NULL,
  `version` varchar(50) DEFAULT NULL,
  `description` varchar(200) NOT NULL,
  `type` varchar(20) NOT NULL,
  `script` varchar(1000) NOT NULL,
  `checksum` int DEFAULT NULL,
  `installed_by` varchar(100) NOT NULL,
  `installed_on` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `execution_time` int NOT NULL,
  `success` tinyint(1) NOT NULL,
  PRIMARY KEY (`installed_rank`),
  KEY `flyway_schema_history_s_idx` (`success`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `user_cards` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `card_id` bigint NOT NULL,
  `kept_count` int NOT NULL DEFAULT '0',
  `first_kept_at` datetime(6) DEFAULT NULL,
  `last_kept_at` datetime(6) DEFAULT NULL,
  `state` varchar(16) NOT NULL DEFAULT 'ACTIVE',
  `graduated_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_cards` (`user_id`,`card_id`),
  KEY `fk_user_cards_card` (`card_id`),
  CONSTRAINT `fk_user_cards_card` FOREIGN KEY (`card_id`) REFERENCES `cards` (`id`),
  CONSTRAINT `fk_user_cards_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `user_devices` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `device_id` varchar(64) NOT NULL,
  `last_seen_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_devices_device` (`device_id`),
  KEY `idx_devices_user` (`user_id`),
  CONSTRAINT `fk_devices_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sync_code_hash` varchar(64) NOT NULL,
  `timezone` varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `remind_at` time DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_sync_code` (`sync_code_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
