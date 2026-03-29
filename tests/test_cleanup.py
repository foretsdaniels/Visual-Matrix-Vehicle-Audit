"""Tests for cleanup logic and retention."""
import os
import tempfile
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


class TestCleanup:
    def _setup_db(self, db_path: str):
        """Initialize a fresh DB at db_path."""
        import sqlite3
        from app.config import DATA_DIR, ARTIFACTS_DIR, LOGS_DIR
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                scope TEXT NOT NULL,
                total_rooms INTEGER DEFAULT 0,
                rooms_with_vehicles INTEGER DEFAULT 0,
                not_in_system INTEGER DEFAULT 0,
                due_outs INTEGER DEFAULT 0,
                stayovers INTEGER DEFAULT 0,
                has_departures INTEGER DEFAULT 0,
                inhouse_filename TEXT,
                departures_filename TEXT,
                allow_multi_label INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS room_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                room_number INTEGER NOT NULL,
                plate TEXT DEFAULT '',
                state TEXT DEFAULT '',
                make_model TEXT DEFAULT '',
                year TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                vehicle_status TEXT,
                has_vehicle_info INTEGER DEFAULT 0,
                vehicle_index INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS session_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def test_cleanup_removes_old_sessions(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        artifacts_dir = str(tmp_path / "artifacts")
        logs_dir = str(tmp_path / "logs")
        os.makedirs(artifacts_dir)
        os.makedirs(logs_dir)

        self._setup_db(db_path)

        import sqlite3
        # Insert one old session (80 hours ago)
        old_sid = "old-session-0001"
        old_time = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
        # Insert one recent session (2 hours ago)
        new_sid = "new-session-0001"
        new_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO audit_sessions (session_id, created_at, scope) VALUES (?,?,?)",
                     (old_sid, old_time, "full"))
        conn.execute("INSERT INTO audit_sessions (session_id, created_at, scope) VALUES (?,?,?)",
                     (new_sid, new_time, "full"))
        conn.commit()
        conn.close()

        # Create artifact dirs
        os.makedirs(os.path.join(artifacts_dir, old_sid))
        os.makedirs(os.path.join(artifacts_dir, new_sid))

        # Patch config and database paths
        with patch("app.config.DB_PATH", db_path), \
             patch("app.config.ARTIFACTS_DIR", artifacts_dir), \
             patch("app.config.LOGS_DIR", logs_dir), \
             patch("app.config.RETENTION_HOURS", 72), \
             patch("app.database.DB_PATH", db_path):
            from app.cleanup import run_cleanup
            run_cleanup()

        # Old session should be gone from DB
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT session_id FROM audit_sessions").fetchall()
        conn.close()
        session_ids = [r[0] for r in rows]
        assert old_sid not in session_ids
        assert new_sid in session_ids

    def test_cleanup_writes_log(self, tmp_path):
        logs_dir = str(tmp_path / "logs")
        db_path = str(tmp_path / "test.db")
        artifacts_dir = str(tmp_path / "artifacts")
        os.makedirs(logs_dir)
        os.makedirs(artifacts_dir)
        self._setup_db(db_path)

        with patch("app.config.DB_PATH", db_path), \
             patch("app.config.ARTIFACTS_DIR", artifacts_dir), \
             patch("app.config.LOGS_DIR", logs_dir), \
             patch("app.config.RETENTION_HOURS", 72), \
             patch("app.database.DB_PATH", db_path):
            from app.cleanup import run_cleanup
            run_cleanup()

        log_file = os.path.join(logs_dir, "cleanup.log")
        assert os.path.exists(log_file)
        content = open(log_file).read()
        assert "cleanup" in content.lower() or "Cleanup" in content

    def test_cleanup_does_not_delete_outside_data_dir(self, tmp_path):
        """Verify cleanup never deletes paths outside ARTIFACTS_DIR."""
        db_path = str(tmp_path / "test.db")
        artifacts_dir = str(tmp_path / "artifacts")
        logs_dir = str(tmp_path / "logs")
        os.makedirs(artifacts_dir)
        os.makedirs(logs_dir)
        self._setup_db(db_path)

        # Create a file outside artifacts dir
        outside_file = str(tmp_path / "important.txt")
        with open(outside_file, "w") as f:
            f.write("do not delete")

        with patch("app.config.DB_PATH", db_path), \
             patch("app.config.ARTIFACTS_DIR", artifacts_dir), \
             patch("app.config.LOGS_DIR", logs_dir), \
             patch("app.config.RETENTION_HOURS", 72), \
             patch("app.database.DB_PATH", db_path):
            from app.cleanup import run_cleanup
            run_cleanup()

        assert os.path.exists(outside_file), "Cleanup must not delete files outside ARTIFACTS_DIR"


class TestRetentionWindow:
    def test_get_old_session_ids_returns_expired(self, tmp_path):
        """Sessions older than retention window should be returned."""
        db_path = str(tmp_path / "test.db")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE audit_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                scope TEXT NOT NULL
            );
        """)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
        new_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute("INSERT INTO audit_sessions VALUES ('old','{}','full')".format(old_time))
        conn.execute("INSERT INTO audit_sessions VALUES ('new','{}','full')".format(new_time))
        conn.commit()
        conn.close()

        with patch("app.database.DB_PATH", db_path):
            from app.database import get_old_session_ids
            expired = get_old_session_ids(72)
        assert "old" in expired
        assert "new" not in expired
