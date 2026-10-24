"""SQLite 数据库：建表与基础访问。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings

DB_PATH = Path(settings.database_path)
if DB_PATH.parent != Path("."):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT NOT NULL DEFAULT '新对话',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role       TEXT NOT NULL,              -- user / assistant / system
    content    TEXT NOT NULL,
    image_urls TEXT NOT NULL DEFAULT '[]', -- JSON 数组
    citations  TEXT NOT NULL DEFAULT '[]', -- JSON 数组：参考来源
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions (id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user   ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_user(username: str, password_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        return cur.lastrowid


def get_user_by_name(username: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return row


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row


def create_session(user_id: int, title: str = "新对话") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (user_id, title) VALUES (?, ?)", (user_id, title)
        )
        return cur.lastrowid


def get_sessions(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()


def add_message(session_id: int, role: str, content: str, image_urls=None, citations=None) -> int:
    import json
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, image_urls, citations) VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                role,
                content,
                json.dumps(image_urls or [], ensure_ascii=False),
                json.dumps(citations or [], ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def get_messages(session_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()


def delete_session(session_id: int, user_id: int) -> bool:
    """删除会话及其全部消息，仅限归属该用户的会话。返回是否删除成功。"""
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cur = conn.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
        )
        return cur.rowcount > 0
