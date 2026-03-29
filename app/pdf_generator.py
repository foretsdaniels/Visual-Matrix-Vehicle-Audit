"""PDF report generator using ReportLab."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from app.parser import RoomEntry
from app.scope import scope_label as get_scope_label

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 0.6 * inch

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _make_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PaTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=4,
            textColor=colors.HexColor("#1a3a5c"),
        ),
        "subtitle": ParagraphStyle(
            "PaSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            spaceAfter=2,
            textColor=colors.HexColor("#2c5282"),
        ),
        "meta": ParagraphStyle(
            "PaMeta",
            parent=styles["Normal"],
            fontSize=9,
            spaceAfter=1,
            textColor=colors.HexColor("#444444"),
        ),
        "cell": ParagraphStyle(
            "PaCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        ),
        "cell_bold": ParagraphStyle(
            "PaCellBold",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
        ),
        "missing": ParagraphStyle(
            "PaMissing",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#c0392b"),
            fontName="Helvetica-Oblique",
        ),
        "due_out": ParagraphStyle(
            "PaDueOut",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#c0392b"),
            fontName="Helvetica-Bold",
        ),
        "stayover": ParagraphStyle(
            "PaStayover",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#27ae60"),
        ),
    }


# ---------------------------------------------------------------------------
# Footer canvas
# ---------------------------------------------------------------------------

class _FooterCanvas:
    def __init__(self, session_id_short: str):
        self.session_id_short = session_id_short

    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        page_text = f"Page {doc.page}"
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 0.35 * inch, page_text)
        session_text = f"Session: {self.session_id_short}"
        canvas.drawString(MARGIN, 0.35 * inch, session_text)
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Table column definitions
# ---------------------------------------------------------------------------

def _build_column_defs(has_departures: bool, has_year: bool) -> tuple[list[str], list[float]]:
    """Return (column_names, column_widths_in_inches)."""
    cols = ["Room"]
    widths = [0.5]
    if has_departures:
        cols.append("Status")
        widths.append(0.7)
    cols += ["State", "Plate", "Make/Model"]
    widths += [0.45, 0.85, 1.7]
    if has_year:
        cols.append("Year")
        widths.append(0.4)
    cols.append("Comment")
    widths.append(1.2)
    return cols, widths


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(
    entries: list[RoomEntry],
    scope: str,
    generated_at: datetime,
    has_departures: bool,
    session_id: str,
    property_name: str = "",
    tz=None,
) -> bytes:
    """Generate PDF and return bytes."""
    buf = io.BytesIO()
    session_id_short = session_id[:8]

    if tz:
        ts_local = generated_at.astimezone(tz)
    else:
        ts_local = generated_at
    timestamp_str = ts_local.strftime("%Y-%m-%d %I:%M %p %Z").strip()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=0.7 * inch,
        title=f"Parking Audit — {get_scope_label(scope)}",
        author=property_name or "Parking Audit Builder",
    )

    styles = _make_styles()
    story = []

    # ---- Header section ----
    if property_name:
        story.append(Paragraph(property_name, styles["subtitle"]))
    story.append(Paragraph("Parking Audit Report", styles["title"]))
    story.append(Paragraph(f"Scope: {get_scope_label(scope)}", styles["subtitle"]))
    story.append(Paragraph(f"Generated: {timestamp_str}", styles["meta"]))
    if has_departures:
        story.append(Paragraph("Includes DUE OUT / STAYOVER status", styles["meta"]))
    story.append(Paragraph(f"Session ID: {session_id_short}", styles["meta"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2c5282")))
    story.append(Spacer(1, 6))

    # ---- Determine if any entry has year data ----
    has_year = any(v.year for e in entries for v in e.vehicles)

    col_names, col_widths_in = _build_column_defs(has_departures, has_year)
    col_widths = [w * inch for w in col_widths_in]

    # ---- Table header row ----
    header_cells = [Paragraph(c, styles["cell_bold"]) for c in col_names]

    table_data = [header_cells]
    row_types: list[str] = ["header"]  # track per-row for styling

    def _cell(text: str, style_key: str = "cell") -> Paragraph:
        return Paragraph(str(text), styles[style_key])

    # ---- Data rows ----
    for entry in entries:
        room_str = str(entry.room_number)
        if not entry.has_vehicle_info:
            # Single row: Not In VM System
            row = [_cell(room_str, "cell_bold")]
            if has_departures:
                status_style = "due_out" if entry.status == "DUE_OUT" else "stayover"
                row.append(_cell(entry.status or "STAYOVER", status_style))
            # Span remaining columns with "Not In VM System"
            remaining = len(col_names) - len(row)
            not_in_sys = _cell("Not In VM System", "missing")
            row.append(not_in_sys)
            # Fill rest with empty
            row += [_cell("") for _ in range(remaining - 1)]
            table_data.append(row)
            row_types.append("missing")
        else:
            first = True
            for v in entry.vehicles:
                if not v.has_vehicle_info:
                    continue
                row = []
                if first:
                    row.append(_cell(room_str, "cell_bold"))
                else:
                    row.append(_cell(""))  # blank room for subsequent vehicles
                if has_departures:
                    if first:
                        status_style = "due_out" if entry.status == "DUE_OUT" else "stayover"
                        row.append(_cell(entry.status or "STAYOVER", status_style))
                    else:
                        row.append(_cell(""))
                row.append(_cell(v.state))
                row.append(_cell(v.plate))
                row.append(_cell(v.make_model))
                if has_year:
                    row.append(_cell(v.year))
                row.append(_cell(v.comment))
                table_data.append(row)
                row_types.append("normal" if entry.status != "DUE_OUT" else "due_out_row")
                first = False

    # ---- Build ReportLab Table ----
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Table styling
    ts = TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ])

    # Alternate row coloring and missing-row highlight
    for i, rtype in enumerate(row_types[1:], start=1):
        if rtype == "missing":
            ts.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fef9f9"))
        elif i % 2 == 0:
            ts.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7faff"))

    tbl.setStyle(ts)
    story.append(tbl)

    footer_fn = _FooterCanvas(session_id_short)
    doc.build(story, onFirstPage=footer_fn, onLaterPages=footer_fn)

    return buf.getvalue()
