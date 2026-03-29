"""Cleanup scheduler — removes sessions older than RETENTION_HOURS."""
from __future__ import annotations

import os
import shutil
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import config

logger = logging.getLogger(__name__)

# Tracks last cleanup time for /health
_last_cleanup: datetime | None = None


def _log_cleanup(message: str) -> None:
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    log_path = os.path.join(config.LOGS_DIR, "cleanup.log")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {message}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        logger.error("Could not write to cleanup.log: %s", e)
    logger.info("Cleanup: %s", message)


def run_cleanup() -> None:
    global _last_cleanup
    from app.database import get_old_session_ids, delete_session

    _log_cleanup("Starting cleanup pass.")
    session_ids = get_old_session_ids(config.RETENTION_HOURS)

    if not session_ids:
        _log_cleanup("No expired sessions found.")
    else:
        for sid in session_ids:
            try:
                delete_session(sid)
                _log_cleanup(f"Deleted session {sid}.")
            except Exception as e:
                _log_cleanup(f"Error deleting session {sid}: {e}")

    # Also delete orphaned artifact directories
    if os.path.isdir(config.ARTIFACTS_DIR):
        real_artifacts = os.path.realpath(config.ARTIFACTS_DIR)
        for entry in os.scandir(config.ARTIFACTS_DIR):
            if not entry.is_dir():
                continue
            real_entry = os.path.realpath(entry.path)
            # Safety: only delete subdirectories directly under ARTIFACTS_DIR
            if os.path.dirname(real_entry) != real_artifacts:
                continue
            # Check if this session still exists in DB
            from app.database import get_session
            if get_session(entry.name) is None:
                try:
                    shutil.rmtree(entry.path)
                    _log_cleanup(f"Removed orphaned artifact dir: {entry.name}")
                except Exception as e:
                    _log_cleanup(f"Error removing orphaned dir {entry.name}: {e}")

    _last_cleanup = datetime.now(timezone.utc)
    _log_cleanup("Cleanup pass complete.")


def get_last_cleanup() -> str | None:
    if _last_cleanup is None:
        return None
    return _last_cleanup.isoformat()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cleanup,
        trigger=IntervalTrigger(hours=config.CLEANUP_INTERVAL_HOURS),
        id="cleanup_job",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Cleanup scheduler started (interval=%.1fh, retention=%dh).",
        config.CLEANUP_INTERVAL_HOURS,
        config.RETENTION_HOURS,
    )
    return scheduler
