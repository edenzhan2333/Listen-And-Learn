"""SQLite 数据库初始化与连接管理"""

import sqlite3
from contextlib import contextmanager
from typing import Generator
from app.config import settings

# 全部建表 SQL
_SCHEMA = """
CREATE TABLE IF NOT EXISTS podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    script_zh_path TEXT,
    script_en_path TEXT,
    audio_zh_path TEXT,
    audio_en_path TEXT,
    duration_zh INTEGER,
    duration_en INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_date TEXT NOT NULL,
    domain TEXT NOT NULL,
    title_zh TEXT NOT NULL,
    title_en TEXT,
    summary_zh TEXT NOT NULL,
    source_url TEXT,
    image_path TEXT,
    wiki_page_path TEXT,
    collected_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    detail TEXT,
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    task_id TEXT,
    step TEXT,
    input TEXT,
    output TEXT,
    tools_used TEXT,
    duration_ms INTEGER,
    status TEXT,
    error TEXT,
    quality_score INTEGER,
    quality_comment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bad_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_log_id INTEGER REFERENCES agent_logs(id),
    category TEXT,
    description TEXT,
    severity TEXT,
    suggestion TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_id INTEGER REFERENCES podcasts(id),
    type TEXT,
    content TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    parameters TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS knowledge_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    domain TEXT,
    category TEXT,
    summary TEXT,
    tags TEXT,
    content TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_pages_fts USING fts5(
    title, summary, content, content='knowledge_pages'
);
"""

# FTS 触发器
_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS knowledge_pages_ai AFTER INSERT ON knowledge_pages BEGIN
    INSERT INTO knowledge_pages_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, new.content);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_pages_ad AFTER DELETE ON knowledge_pages BEGIN
    INSERT INTO knowledge_pages_fts(knowledge_pages_fts, rowid, title, summary, content)
    VALUES('delete', old.id, old.title, old.summary, old.content);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_pages_au AFTER UPDATE ON knowledge_pages BEGIN
    INSERT INTO knowledge_pages_fts(knowledge_pages_fts, rowid, title, summary, content)
    VALUES('delete', old.id, old.title, old.summary, old.content);
    INSERT INTO knowledge_pages_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, new.content);
END;
"""


def init_db():
    """初始化数据库 —— 建表、触发器、种子数据"""
    conn = sqlite3.connect(str(settings.DB_PATH))
    conn.executescript(_SCHEMA)
    conn.executescript(_TRIGGERS)
    # 种子：插入默认 Agent 配置（如果不存在）
    _seed_agent_configs(conn)
    conn.commit()
    conn.close()


def _seed_agent_configs(conn):
    """为每个 Agent 插入默认 prompt 配置"""
    from app.harness.prompts import DEFAULT_PROMPTS
    cur = conn.execute("SELECT COUNT(*) FROM agent_configs")
    if cur.fetchone()[0] > 0:
        return
    for name, prompt in DEFAULT_PROMPTS.items():
        conn.execute(
            "INSERT INTO agent_configs (agent_name, prompt_version, prompt_text, parameters, active) "
            "VALUES (?, 'v1', ?, '{}', 1)",
            (name, prompt)
        )


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(str(settings.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
