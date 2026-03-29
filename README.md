# Parking Audit Builder

Self-hosted web application for generating Zebra ZPL parking audit labels and PDF reports from Visual Matrix (VM) In-House Guests Excel exports.

**Public URL:** https://parkaudit.warshot32456.com

---

## Features

- Upload VM In-House Guests `.xlsx` / `.xls` export
- Optional Departures file to tag rooms as **DUE OUT** vs **STAYOVER**
- Three scopes: **100/200s**, **300/400s**, **Full List**
- Generates **ZPL labels** (4"×8", Zebra ZP450 / 203 DPI) — single `.zpl` or `.zip`
- Generates **PDF report** with full room/vehicle table
- Live **Dashboard** with auto-refresh and filters
- **Session history** (72-hour retention) with per-session downloads
- Automatic cleanup of old sessions/artifacts

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- `pip install -r requirements.txt`

```bash
# Clone and enter the repo
cd Visual-Matrix-Vehicle-Audit

# (Optional) create .env from example
cp .env.example .env

# Run locally
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

App available at: http://localhost:8000

---

## Docker Run

```bash
docker build -t parking-audit .
docker run -d \
  -e TZ="America/Chicago" \
  -e PROPERTY_NAME="Buccaneer Inn" \
  -v "$(pwd)/data:/app/data" \
  -p 8000:8000 \
  --name parking-audit \
  parking-audit
```

---

## Docker Compose (with Cloudflare Tunnel)

### 1. Create `.env`

```bash
cp .env.example .env
# Edit .env and set CLOUDFLARED_TUNNEL_TOKEN
```

### 2. Start services

```bash
docker compose up -d
```

The app starts first; Cloudflare Tunnel waits for the healthcheck to pass before connecting.

### 3. Verify

```bash
docker compose ps
docker compose logs -f parking-audit
curl http://localhost:8000/health   # if you have a port mapped for testing
```

---

## Cloudflare Tunnel Setup

1. Log in to the [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com)
2. Go to **Access → Tunnels → Create a Tunnel**
3. Name it (e.g., `parking-audit`)
4. Copy the **Tunnel Token** and add it to `.env`:
   ```
   CLOUDFLARED_TUNNEL_TOKEN=eyJ...
   ```
5. Under **Public Hostnames**, add:
   | Subdomain | Domain | Path | Service |
   |-----------|--------|------|---------|
   | parkaudit | warshot32456.com | | `http://parking-audit:8000` |
6. Save and run `docker compose up -d`

The app will be accessible at: **https://parkaudit.warshot32456.com**

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `America/Chicago` | Timezone for timestamps |
| `PROPERTY_NAME` | _(empty)_ | Hotel name displayed in headers |
| `RETENTION_HOURS` | `72` | How long to keep session data (hours) |
| `CLEANUP_INTERVAL_HOURS` | `12` | How often to run cleanup |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Port |
| `CLOUDFLARED_TUNNEL_TOKEN` | — | Cloudflare tunnel token (Docker Compose) |

---

## Usage Guide

### Generating an Audit

1. Go to **/** (Upload page)
2. Upload the VM **In-House Guests** export (`.xlsx` or `.xls`)
3. _(Optional)_ Upload a **Departures** file to enable DUE OUT / STAYOVER tagging
4. Select scope: **100/200s**, **300/400s**, or **Full List**
5. Toggle **Allow multi-label split** (default: on)
6. Click **Generate Audit**

### Downloading Labels

After generation you'll see the **Preview** page with:

- **Download PDF Report** — full tabular report
- **Download ZPL Labels** — `.zpl` (single label) or `.zip` (multiple labels)

### Printing ZPL Labels

The Zebra printer does not need to be on the same network as the server. Download the `.zpl` or `.zip` file to a computer that has network access to the printer, then:

```bash
# On Linux/Mac (single label):
cat parking_audit_100_200s.zpl | nc <printer-ip> 9100

# Or use Zebra Browser Print, ZebraDesigner, or any ZPL-aware tool
# On Windows: copy <file.zpl> \\<printer-ip>\ZPL
```

For ZIP files, extract and send each `.zpl` file in order.

### Session History

Visit **/sessions** to see all sessions from the last 72 hours. Each session has:
- View Dashboard
- Preview
- Download PDF
- Download ZPL
- Delete

---

## Development

### Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Project Structure

```
app/
  config.py          # Env var configuration
  database.py        # SQLite CRUD
  parser.py          # Excel parsing (in-house + departures)
  scope.py           # Scope filtering, room grouping
  zpl_generator.py   # ZPL label generation
  pdf_generator.py   # PDF report generation (ReportLab)
  cleanup.py         # Retention/cleanup scheduler
  main.py            # FastAPI routes
  templates/         # Jinja2 HTML templates
  static/            # CSS and JavaScript
tests/               # Unit tests
data/                # Runtime data (SQLite DB, artifacts, logs)
```

---

## Health Check

```
GET /health
```

Returns:
```json
{
  "status": "ok",
  "sqlite_reachable": true,
  "data_writable": true,
  "last_cleanup": "2026-03-29T06:00:00+00:00",
  "disk_free_mb": 4200.5
}
```

---

## Notes

- `.xls` files are parsed via `xlrd==1.2.0`. If xlrd is unavailable, LibreOffice headless conversion is attempted automatically.
- Uploads are processed in-memory and not stored to disk.
- All generated artifacts (PDF/ZPL) are stored under `data/artifacts/{session_id}/`.
- Cleanup removes sessions and artifacts older than `RETENTION_HOURS` (default 72h). Cleanup log is written to `data/logs/cleanup.log`.
