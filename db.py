from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "conversation_memory.db"


class ConversationDB:
    """SQLite store for interview sessions and conversation messages."""

    def __init__(self, db_path: Path = DB_PATH):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT    NOT NULL,
                    ended_at   TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    role       TEXT    NOT NULL CHECK(role IN ('ai', 'user')),
                    content    TEXT    NOT NULL,
                    created_at TEXT    NOT NULL
                );
            """)
            self._conn.commit()

    def start_session(self) -> int:
        now = datetime.utcnow().isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions (started_at) VALUES (?)", (now,)
            )
            self._conn.commit()
            return cur.lastrowid

    def end_session(self, session_id: int):
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?", (now, session_id)
            )
            self._conn.commit()

    def add_message(self, session_id: int, role: str, content: str):
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            self._conn.commit()

    def close(self):
        self._conn.close()
