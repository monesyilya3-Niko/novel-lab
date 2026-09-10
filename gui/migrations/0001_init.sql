-- 0001_init.sql — 初始化 schema（6 张表 + 索引）
--
-- 版本号 = 文件名序号（0001）。由 gui/db.apply_migrations() 按序执行缺失版本，
-- 每条迁移在单事务内执行，失败回滚。所有 CREATE 使用 IF NOT EXISTS 保证幂等。
--
-- 说明：PRAGMA 由 db.py 在连接层统一设置（foreign_keys=ON / WAL / busy_timeout），
-- 此文件只放 DDL，避免在迁移事务中途切换 journal_mode 造成歧义。

CREATE TABLE IF NOT EXISTS schema_migrations (
    version      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    applied_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id       TEXT    NOT NULL UNIQUE,
    title         TEXT    NOT NULL,
    source_path   TEXT,
    genre         TEXT,
    status        TEXT    NOT NULL DEFAULT 'idle',
    imported_at   TEXT,
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);

CREATE TABLE IF NOT EXISTS assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_key     TEXT    NOT NULL UNIQUE,
    kind          TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    path          TEXT    NOT NULL UNIQUE,
    book_id       TEXT,
    genre         TEXT,
    size          INTEGER,
    mtime         REAL,
    meta_json     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_kind   ON assets(kind);
CREATE INDEX IF NOT EXISTS idx_assets_book   ON assets(book_id);
CREATE INDEX IF NOT EXISTS idx_assets_genre  ON assets(genre);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_key    TEXT    NOT NULL UNIQUE,
    type          TEXT    NOT NULL,
    book_id       TEXT,
    path          TEXT    NOT NULL UNIQUE,
    title         TEXT,
    char_count    INTEGER,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reports_book ON reports(book_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(type);

CREATE TABLE IF NOT EXISTS analysis_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id       TEXT    NOT NULL UNIQUE,
    status        TEXT    NOT NULL DEFAULT 'idle',
    genre         TEXT,
    model_id      TEXT,
    batch_size    INTEGER,
    cursor        TEXT    NOT NULL DEFAULT '',
    batch_state   TEXT    NOT NULL DEFAULT '{}',
    state_revision INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON analysis_tasks(status);

CREATE TABLE IF NOT EXISTS genres (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    display_name  TEXT,
    -- 题材**来源** kind，枚举：genre_pack / prose_card / book（「题材包优先」）。
    -- L1 契约：非上述枚举的**资产** kind（voice/commercial/craft/structure/trope）
    -- 一律不得写入本列——由 migrate._sanitize_genre_kind + _upsert_genre 优先级裁决保证。
    kind          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
