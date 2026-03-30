import os
from zoneinfo import ZoneInfo

TZ = os.environ.get("TZ", "America/New_York")
PROPERTY_NAME = os.environ.get("PROPERTY_NAME", "Buccaneer Inn")
RETENTION_HOURS = int(os.environ.get("RETENTION_HOURS", "72"))
CLEANUP_INTERVAL_HOURS = float(os.environ.get("CLEANUP_INTERVAL_HOURS", "12"))
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "audit.db")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

try:
    TIMEZONE = ZoneInfo(TZ)
except Exception:
    TIMEZONE = ZoneInfo("America/New_York")
