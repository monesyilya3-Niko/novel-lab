-- 0004: 小说项目元数据（Project Metadata & Platform Binding）
-- 持久化存储每个作品的目标发布平台、核心题材、字数目标与简介，打通全流程自动适配。

CREATE TABLE IF NOT EXISTS writing_projects_meta (
    project         TEXT PRIMARY KEY,
    platform        TEXT NOT NULL DEFAULT 'fanqie',
    genre           TEXT NOT NULL DEFAULT 'general',
    target_words    INTEGER NOT NULL DEFAULT 1000000,
    summary         TEXT NOT NULL DEFAULT '',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_projects_meta_platform
    ON writing_projects_meta(platform);
CREATE INDEX IF NOT EXISTS idx_projects_meta_genre
    ON writing_projects_meta(genre);
