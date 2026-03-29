"""SQLite database layer using synchronous sqlite3."""
import sqlite3
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from app.config import DB_PATH, DATA_DIR, ARTIFACTS_DIR, LOGS_DIR


def _ensure_dirs() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
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


def init_db() -> None:
    _ensure_dirs()
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_sessions (
                session_id        TEXT PRIMARY KEY,
                created_at        TEXT NOT NULL,
                scope             TEXT NOT NULL,
                total_rooms       INTEGER DEFAULT 0,
                rooms_with_vehicles INTEGER DEFAULT 0,
                not_in_system     INTEGER DEFAULT 0,
                due_outs          INTEGER DEFAULT 0,
                stayovers         INTEGER DEFAULT 0,
                has_departures    INTEGER DEFAULT 0,
                inhouse_filename  TEXT,
                departures_filename TEXT,
                allow_multi_label INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS room_records (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                room_number     INTEGER NOT NULL,
                plate           TEXT DEFAULT '',
                state           TEXT DEFAULT '',
                make_model      TEXT DEFAULT '',
                year            TEXT DEFAULT '',
                comment         TEXT DEFAULT '',
                vehicle_status  TEXT,
                has_vehicle_info INTEGER DEFAULT 0,
                vehicle_index   INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES audit_sessions(session_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS session_artifacts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                artifact_type   TEXT NOT NULL,
                file_path       TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES audit_sessions(session_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_room_records_session
                ON room_records(session_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_session
                ON session_artifacts(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_created
                ON audit_sessions(created_at);
        """)


def create_session(
    session_id: str,
    scope: str,
    total_rooms: int,
    rooms_with_vehicles: int,
    not_in_system: int,
    due_outs: int,
    stayovers: int,
    has_departures: bool,
    inhouse_filename: str,
    departures_filename: Optional[str],
    allow_multi_label: bool,
    created_at: Optional[str] = None,
) -> None:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO audit_sessions
               (session_id, created_at, scope, total_rooms, rooms_with_vehicles,
                not_in_system, due_outs, stayovers, has_departures,
                inhouse_filename, departures_filename, allow_multi_label)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, created_at, scope, total_rooms, rooms_with_vehicles,
                not_in_system, due_outs, stayovers, int(has_departures),
                inhouse_filename, departures_filename, int(allow_multi_label),
            ),
        )


def save_room_records(session_id: str, records: list[dict]) -> None:
    """records: list of dicts with keys matching room_records columns."""
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO room_records
               (session_id, room_number, plate, state, make_model, year,
                comment, vehicle_status, has_vehicle_info, vehicle_index)
               VALUES (:session_id,:room_number,:plate,:state,:make_model,
                       :year,:comment,:vehicle_status,:has_vehicle_info,:vehicle_index)""",
            records,
        )


def save_artifact(session_id: str, artifact_type: str, file_path: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO session_artifacts (session_id, artifact_type, file_path, created_at)
               VALUES (?,?,?,?)""",
            (session_id, artifact_type, file_path, created_at),
        )


def get_session(session_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audit_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def get_sessions(retention_hours: int = 72) -> list[dict]:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_sessions WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_room_records(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM room_records
               WHERE session_id=?
               ORDER BY room_number, vehicle_index""",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_artifacts(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM session_artifacts WHERE session_id=?", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_session(session_id: str) -> None:
    """Delete session DB record + artifacts directory."""
    session_dir = os.path.join(ARTIFACTS_DIR, session_id)
    # Safety: only delete if within ARTIFACTS_DIR
    real_session_dir = os.path.realpath(session_dir)
    real_artifacts_dir = os.path.realpath(ARTIFACTS_DIR)
    if real_session_dir.startswith(real_artifacts_dir + os.sep) or real_session_dir == real_artifacts_dir:
        if os.path.isdir(session_dir):
            shutil.rmtree(session_dir)
    with get_conn() as conn:
        conn.execute("DELETE FROM audit_sessions WHERE session_id=?", (session_id,))


def get_old_session_ids(retention_hours: int) -> list[str]:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT session_id FROM audit_sessions WHERE created_at < ?", (cutoff,)
        ).fetchall()
        return [r["session_id"] for r in rows]


def db_reachable() -> bool:
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
