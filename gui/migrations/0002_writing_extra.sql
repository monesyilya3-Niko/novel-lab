-- 0002: 写作增值功能（v2.0.2）
-- 大纲 / 人物卡 / 灵感便签 / 每日码字统计。幂等建表。

CREATE TABLE IF NOT EXISTS writing_outlines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'chapter',   -- volume | chapter
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'planned',   -- planned | writing | done
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_writing_outlines_project
    ON writing_outlines(project, sort_order, id);

CREATE TABLE IF NOT EXISTS writing_characters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    extra       TEXT NOT NULL DEFAULT '{}',        -- JSON：年龄/外貌/性格等扩展字段
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_writing_characters_project
    ON writing_characters(project, name);

CREATE TABLE IF NOT EXISTS writing_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_writing_notes_project
    ON writing_notes(project, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS writing_daily_stats (
    date        TEXT NOT NULL,                     -- YYYY-MM-DD（本地日期）
    project     TEXT NOT NULL,
    words       INTEGER NOT NULL DEFAULT 0,        -- 当日新增字数
    chapters    INTEGER NOT NULL DEFAULT 0,        -- 当日新增章节数
    PRIMARY KEY (date, project)
);
