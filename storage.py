from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path


class Storage:
    """Minimal storage. Sensitive message text is deliberately not saved."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    chat_type TEXT NOT NULL DEFAULT 'private',
                    daily_enabled INTEGER NOT NULL DEFAULT 0,
                    last_daily_date TEXT,
                    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS intent_stats (
                    intent TEXT PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def upsert_user(
        self,
        chat_id: int,
        user_id: int | None,
        username: str,
        first_name: str,
        chat_type: str,
    ) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO users(chat_id, user_id, username, first_name, chat_type)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    username=excluded.username,
                    first_name=excluded.first_name,
                    chat_type=excluded.chat_type,
                    last_seen=CURRENT_TIMESTAMP
                """,
                (chat_id, user_id, username[:100], first_name[:100], chat_type[:30]),
            )

    def log_intent(self, intent: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO intent_stats(intent, count) VALUES (?, 1)
                ON CONFLICT(intent) DO UPDATE SET count=count + 1
                """,
                (intent,),
            )

    def toggle_daily(self, chat_id: int) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT daily_enabled FROM users WHERE chat_id=?", (chat_id,)
            ).fetchone()
            enabled = not bool(row[0]) if row else True
            if row:
                db.execute(
                    "UPDATE users SET daily_enabled=?, last_daily_date=NULL WHERE chat_id=?",
                    (int(enabled), chat_id),
                )
            else:
                db.execute(
                    "INSERT INTO users(chat_id, daily_enabled) VALUES (?, ?)",
                    (chat_id, int(enabled)),
                )
            return enabled

    def daily_enabled(self, chat_id: int) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT daily_enabled FROM users WHERE chat_id=?", (chat_id,)
            ).fetchone()
            return bool(row[0]) if row else False

    def disable_daily(self, chat_id: int) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE users SET daily_enabled=0 WHERE chat_id=?",
                (chat_id,),
            )

    def subscribers_due(self, today: date) -> list[int]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT chat_id FROM users
                WHERE daily_enabled=1
                  AND chat_type='private'
                  AND (last_daily_date IS NULL OR last_daily_date != ?)
                """,
                (today.isoformat(),),
            ).fetchall()
            return [int(row[0]) for row in rows]

    def mark_daily_sent(self, chat_id: int, today: date) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE users SET last_daily_date=? WHERE chat_id=?",
                (today.isoformat(), chat_id),
            )

    def get_offset(self) -> int | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT value FROM state WHERE key='offset'").fetchone()
            return int(row[0]) if row else None

    def set_offset(self, offset: int) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO state(key, value) VALUES ('offset', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(offset),),
            )

    def stats(self) -> tuple[int, list[tuple[str, int]]]:
        with self._lock, self._connect() as db:
            users = int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            rows = db.execute(
                "SELECT intent, count FROM intent_stats ORDER BY count DESC"
            ).fetchall()
            return users, [(str(row[0]), int(row[1])) for row in rows]
