from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from storage import Storage


class StorageTests(unittest.TestCase):
    def test_daily_subscription_and_due_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite3")
            storage.upsert_user(10, 20, "user", "Имя", "private")
            self.assertTrue(storage.toggle_daily(10))
            today = date(2026, 7, 10)
            self.assertEqual(storage.subscribers_due(today), [10])
            storage.mark_daily_sent(10, today)
            self.assertEqual(storage.subscribers_due(today), [])

    def test_message_text_is_not_a_database_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite3"
            storage = Storage(path)
            storage.log_intent("panic")
            users, stats = storage.stats()
            self.assertEqual(users, 0)
            self.assertEqual(stats, [("panic", 1)])


if __name__ == "__main__":
    unittest.main()

