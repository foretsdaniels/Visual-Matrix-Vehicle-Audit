"""FastAPI application — Parking Audit Builder."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app import database as db
from app.cleanup import get_last_cleanup, run_cleanup, start_scheduler
from app.parser import parse_inhouse_excel, parse_departures_excel
from app.pdf_generator import generate_pdf
from app.scope import (
    build_room_entries, build_label_preview_lines,
    compute_counts, scope_label,
)
from app.zpl_generator import generate_zpl, zpl_to_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "app", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

app = FastAPI(title="Parking Audit Builder", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def startup_event():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.ARTIFACTS_DIR, exist_ok=True)
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    db.init_db()
    run_cleanup()  # immediate cleanup on startup
    start_scheduler()
    logger.info("Parking Audit Builder started.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _artifact_dir(session_id: str) -> str:
    d = os.path.join(config.ARTIFACTS_DIR, session_id)
    os.makedirs(d, exist_ok=True)
    return d


def _get_session_or_404(session_id: str) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _entries_from_db(session_id: str, session: dict) -> list:
    """Reconstruct RoomEntry list from DB for a session."""
    from app.parser import VehicleRecord, RoomEntry
    records = db.get_room_records(session_id)
    room_map: dict[int, RoomEntry] = {}
    for rec in records:
        rn = rec["room_number"]
        if rn not in room_map:
            room_map[rn] = RoomEntry(
                room_number=rn,
                vehicles=[],
                status=rec["vehicle_status"],
            )
        # Only add vehicle if has_vehicle_info is true
        if rec["has_vehicle_info"]:
            room_map[rn].vehicles.append(VehicleRecord(
                room_number=rn,
                plate=rec["plate"] or "",
                state=rec["state"] or "",
                make_model=rec["make_model"] or "",
                year=rec["year"] or "",
                comment=rec["comment"] or "",
            ))
        else:
            # Ensure at least one empty VehicleRecord so has_vehicle_info works
            if not room_map[rn].vehicles:
                room_map[rn].vehicles.append(VehicleRecord(room_number=rn))
    return sorted(room_map.values(), key=lambda e: e.room_number)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "property_name": config.PROPERTY_NAME,
    })


@app.post("/generate")
async def generate(
    request: Request,
    inhouse_file: UploadFile = File(...),
    departures_file: Optional[UploadFile] = File(None),
    scope: str = Form(...),
    allow_multi_label: str = Form("on"),
):
    multi = allow_multi_label.lower() in ("on", "true", "1", "yes")
    errors: list[str] = []

    # ---- Read files ----
    inhouse_bytes = await inhouse_file.read()
    departures_bytes = None
    if departures_file and departures_file.filename:
        departures_bytes = await departures_file.read()

    # ---- Parse in-house ----
    try:
        vehicle_records = parse_inhouse_excel(inhouse_bytes, inhouse_file.filename)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "property_name": config.PROPERTY_NAME,
            "error": f"Error parsing in-house file: {e}",
        }, status_code=400)

    # ---- Parse departures ----
    due_out_rooms: Optional[set[int]] = None
    has_departures = False
    if departures_bytes:
        try:
            due_out_rooms = parse_departures_excel(
                departures_bytes,
                departures_file.filename,
            )
            has_departures = True
        except Exception as e:
            errors.append(f"Warning: Could not parse departures file ({e}). Proceeding without.")

    # ---- Build room entries ----
    entries = build_room_entries(vehicle_records, scope, due_out_rooms)

    if not entries:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "property_name": config.PROPERTY_NAME,
            "error": f"No rooms found for scope '{scope}'. Check your in-house file.",
        }, status_code=400)

    counts = compute_counts(entries)
    now = _now()
    session_id = str(uuid.uuid4())

    # ---- Generate ZPL ----
    zpl_blocks = generate_zpl(
        entries=entries,
        scope=scope,
        generated_at=now,
        has_departures=has_departures,
        allow_multi_label=multi,
        property_name=config.PROPERTY_NAME,
        tz=config.TIMEZONE,
    )
    zpl_bytes, zpl_filename = zpl_to_file(zpl_blocks, scope_label(scope))

    # ---- Generate PDF ----
    pdf_bytes = generate_pdf(
        entries=entries,
        scope=scope,
        generated_at=now,
        has_departures=has_departures,
        session_id=session_id,
        property_name=config.PROPERTY_NAME,
        tz=config.TIMEZONE,
    )

    # ---- Save artifacts ----
    art_dir = _artifact_dir(session_id)
    pdf_path = os.path.join(art_dir, "report.pdf")
    zpl_path = os.path.join(art_dir, zpl_filename)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    with open(zpl_path, "wb") as f:
        f.write(zpl_bytes)

    # ---- Save to DB ----
    db.create_session(
        session_id=session_id,
        scope=scope,
        total_rooms=counts["total_rooms"],
        rooms_with_vehicles=counts["rooms_with_vehicles"],
        not_in_system=counts["not_in_system"],
        due_outs=counts["due_outs"],
        stayovers=counts["stayovers"],
        has_departures=has_departures,
        inhouse_filename=inhouse_file.filename,
        departures_filename=departures_file.filename if departures_bytes else None,
        allow_multi_label=multi,
        created_at=now.isoformat(),
    )

    # Save room records
    db_records = []
    for entry in entries:
        if not entry.vehicles:
            db_records.append({
                "session_id": session_id,
                "room_number": entry.room_number,
                "plate": "", "state": "", "make_model": "", "year": "", "comment": "",
                "vehicle_status": entry.status,
                "has_vehicle_info": 0,
                "vehicle_index": 0,
            })
        else:
            for vi, v in enumerate(entry.vehicles):
                db_records.append({
                    "session_id": session_id,
                    "room_number": entry.room_number,
                    "plate": v.plate,
                    "state": v.state,
                    "make_model": v.make_model,
                    "year": v.year,
                    "comment": v.comment,
                    "vehicle_status": entry.status,
                    "has_vehicle_info": 1 if v.has_vehicle_info else 0,
                    "vehicle_index": vi,
                })
    db.save_room_records(session_id, db_records)
    db.save_artifact(session_id, "pdf", pdf_path)
    db.save_artifact(session_id, "zpl" if zpl_filename.endswith(".zpl") else "zip", zpl_path)

    return RedirectResponse(url=f"/preview/{session_id}", status_code=303)


@app.get("/preview/{session_id}", response_class=HTMLResponse)
def preview(request: Request, session_id: str):
    session = _get_session_or_404(session_id)
    entries = _entries_from_db(session_id, session)
    has_departures = bool(session["has_departures"])

    preview_lines = build_label_preview_lines(entries, has_departures)

    # Check artifact existence
    artifacts = db.get_artifacts(session_id)
    has_pdf = any(a["artifact_type"] == "pdf" for a in artifacts)
    has_zpl = any(a["artifact_type"] in ("zpl", "zip") for a in artifacts)

    return templates.TemplateResponse("preview.html", {
        "request": request,
        "session": session,
        "preview_lines": preview_lines,
        "has_pdf": has_pdf,
        "has_zpl": has_zpl,
        "scope_label": scope_label(session["scope"]),
        "property_name": config.PROPERTY_NAME,
    })


@app.get("/download/{session_id}/pdf")
def download_pdf(session_id: str):
    _get_session_or_404(session_id)
    artifacts = db.get_artifacts(session_id)
    pdf_artifact = next((a for a in artifacts if a["artifact_type"] == "pdf"), None)
    if not pdf_artifact or not os.path.exists(pdf_artifact["file_path"]):
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(
        path=pdf_artifact["file_path"],
        filename=f"parking_audit_{session_id[:8]}.pdf",
        media_type="application/pdf",
    )


@app.get("/download/{session_id}/zpl")
def download_zpl(session_id: str):
    _get_session_or_404(session_id)
    artifacts = db.get_artifacts(session_id)
    zpl_artifact = next(
        (a for a in artifacts if a["artifact_type"] in ("zpl", "zip")), None
    )
    if not zpl_artifact or not os.path.exists(zpl_artifact["file_path"]):
        raise HTTPException(status_code=404, detail="ZPL file not found.")
    art_type = zpl_artifact["artifact_type"]
    media_type = "application/zip" if art_type == "zip" else "text/plain"
    filename = os.path.basename(zpl_artifact["file_path"])
    return FileResponse(
        path=zpl_artifact["file_path"],
        filename=filename,
        media_type=media_type,
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, session_id: Optional[str] = None):
    if not session_id:
        # Use the most recent session
        sessions = db.get_sessions(config.RETENTION_HOURS)
        if sessions:
            session_id = sessions[0]["session_id"]
    session = db.get_session(session_id) if session_id else None
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "session": session,
        "session_id": session_id,
        "scope_label": scope_label(session["scope"]) if session else "",
        "property_name": config.PROPERTY_NAME,
    })


@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request):
    session_list = db.get_sessions(config.RETENTION_HOURS)
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "sessions": session_list,
        "property_name": config.PROPERTY_NAME,
        "scope_label_fn": scope_label,
    })


@app.delete("/sessions/{session_id}")
def delete_session_route(session_id: str):
    _get_session_or_404(session_id)
    db.delete_session(session_id)
    return JSONResponse({"status": "deleted", "session_id": session_id})


@app.get("/api/session/{session_id}")
def api_session_data(session_id: str):
    session = _get_session_or_404(session_id)
    records = db.get_room_records(session_id)
    return JSONResponse({
        "session": dict(session),
        "records": records,
        "scope_label": scope_label(session["scope"]),
    })


@app.get("/api/sessions")
def api_sessions():
    return JSONResponse(db.get_sessions(config.RETENTION_HOURS))


@app.get("/health")
def health():
    import shutil as _shutil
    db_ok = db.db_reachable()
    data_writable = os.access(config.DATA_DIR, os.W_OK)
    total, used, free = _shutil.disk_usage(config.DATA_DIR)
    return JSONResponse({
        "status": "ok" if (db_ok and data_writable) else "degraded",
        "sqlite_reachable": db_ok,
        "data_writable": data_writable,
        "last_cleanup": get_last_cleanup(),
        "disk_free_mb": round(free / 1024 / 1024, 1),
    })


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=False,
    )
