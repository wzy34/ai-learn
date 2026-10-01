-- MySQL 8.x initialization for the AI Quiz user system.
-- This script is safe to run repeatedly against a new or existing ai_learn database.

CREATE DATABASE IF NOT EXISTS `ai_learn`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `ai_learn`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `openid` VARCHAR(64) NOT NULL,
  `nickname` VARCHAR(100) NOT NULL DEFAULT '学习者',
  `avatar_url` VARCHAR(500) NOT NULL DEFAULT '',
  `total_xp` INT UNSIGNED NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_openid` (`openid`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `quiz_sessions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `quiz_id` VARCHAR(64) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `summary` TEXT NOT NULL,
  `user_input` TEXT NOT NULL,
  `questions_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_quiz_sessions_quiz_id` (`quiz_id`),
  UNIQUE KEY `uk_quiz_sessions_quiz_user` (`quiz_id`, `user_id`),
  KEY `idx_quiz_sessions_user_created_at` (`user_id`, `created_at`),
  CONSTRAINT `fk_quiz_sessions_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `answer_records` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `quiz_id` VARCHAR(64) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `records_json` JSON NOT NULL,
  `total_questions` SMALLINT UNSIGNED NOT NULL,
  `correct_count` SMALLINT UNSIGNED NOT NULL,
  `accuracy` DECIMAL(5,2) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_answer_records_quiz_id` (`quiz_id`),
  KEY `idx_answer_records_user_id` (`user_id`),
  CONSTRAINT `chk_answer_records_total_questions`
    CHECK (`total_questions` > 0),
  CONSTRAINT `chk_answer_records_correct_count`
    CHECK (`correct_count` <= `total_questions`),
  CONSTRAINT `chk_answer_records_accuracy`
    CHECK (`accuracy` >= 0 AND `accuracy` <= 100),
  CONSTRAINT `fk_answer_records_quiz_session`
    FOREIGN KEY (`quiz_id`, `user_id`)
    REFERENCES `quiz_sessions` (`quiz_id`, `user_id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `reports` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `quiz_id` VARCHAR(64) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `report_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_reports_quiz_id` (`quiz_id`),
  KEY `idx_reports_user_id` (`user_id`),
  CONSTRAINT `fk_reports_quiz_session`
    FOREIGN KEY (`quiz_id`, `user_id`)
    REFERENCES `quiz_sessions` (`quiz_id`, `user_id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- No sample user data is inserted. Real users are created from their WeChat openid on first login.
