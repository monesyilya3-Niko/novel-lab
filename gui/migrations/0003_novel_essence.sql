-- 0003: 小说精华数据库（Novel Essence Database）
-- 存储已拆解小说的五维精华资产、伏笔回收图谱、精读进度与长篇任务游标。

CREATE TABLE IF NOT EXISTS essence_books (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id            TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    source_path        TEXT NOT NULL DEFAULT '',
    genre              TEXT NOT NULL DEFAULT 'general',
    platform           TEXT NOT NULL DEFAULT 'general',
    total_chapters     INTEGER NOT NULL DEFAULT 0,
    total_chars        INTEGER NOT NULL DEFAULT 0,
    analyzed_chapters  INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'ready',
    meta_json          TEXT NOT NULL DEFAULT '{}',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_essence_books_genre
    ON essence_books(genre);
CREATE INDEX IF NOT EXISTS idx_essence_books_platform
    ON essence_books(platform);

CREATE TABLE IF NOT EXISTS essence_assets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id            TEXT NOT NULL,
    category           TEXT NOT NULL,
    title              TEXT NOT NULL,
    summary            TEXT NOT NULL DEFAULT '',
    content            TEXT NOT NULL,
    tags               TEXT NOT NULL DEFAULT '',
    genre              TEXT NOT NULL DEFAULT 'general',
    platform           TEXT NOT NULL DEFAULT 'general',
    rating             INTEGER NOT NULL DEFAULT 5,
    user_note          TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_essence_assets_book
    ON essence_assets(book_id, category);
CREATE INDEX IF NOT EXISTS idx_essence_assets_category
    ON essence_assets(category);
CREATE INDEX IF NOT EXISTS idx_essence_assets_genre
    ON essence_assets(genre);

CREATE TABLE IF NOT EXISTS essence_chains (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id            TEXT NOT NULL,
    hook_chapter       INTEGER NOT NULL DEFAULT 1,
    payoff_chapter     INTEGER NOT NULL DEFAULT 1,
    hook_text          TEXT NOT NULL DEFAULT '',
    payoff_text        TEXT NOT NULL DEFAULT '',
    clue_name          TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'resolved',
    analysis           TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_essence_chains_book
    ON essence_chains(book_id, hook_chapter);

CREATE TABLE IF NOT EXISTS essence_tasks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id            TEXT NOT NULL UNIQUE,
    status             TEXT NOT NULL DEFAULT 'idle',
    current_chapter    INTEGER NOT NULL DEFAULT 0,
    total_chapters     INTEGER NOT NULL DEFAULT 0,
    last_error         TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_essence_tasks_status
    ON essence_tasks(status);
