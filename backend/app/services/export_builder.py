from __future__ import annotations

import json
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.assessment_loader import AssessmentDefinition, PracticeDefinition
from app.models import AssessmentSession, PracticeResponse

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECT_FONT_DIR = _BACKEND_ROOT / "fonts"

# Typographic / unicode characters that break PDF core fonts (Helvetica); map to ASCII-ish.
_UNICODE_FALLBACK_CHARS = str.maketrans(
    {
        "\u2011": "-",  # non-breaking hyphen (common in pasted Word text)
        "\u2010": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u00ad": "",  # soft hyphen
        "\u2018": "\u0027",
        "\u2019": "\u0027",
        "\u201c": "\u0022",
        "\u201d": "\u0022",
        "\u00ab": "\u0022",
        "\u00bb": "\u0022",
        "\u2026": "...",
        "\u00a0": " ",
        "\u202f": " ",
        "\u2009": " ",
        "\u200a": "",
        "\ufeff": "",
    }
)


def _pdf_text_for_font(text: str, *, unicode_font: bool) -> str:
    """Core PDF fonts only support Latin-1; DejaVu supports full Unicode."""
    if not text:
        return text
    if unicode_font:
        return text
    s = unicodedata.normalize("NFKC", text).translate(_UNICODE_FALLBACK_CHARS)
    return s.encode("latin-1", errors="replace").decode("latin-1")


class ReportPDF(FPDF):
    """Uses bundled DejaVu when both TTFs are present; otherwise core Helvetica everywhere (incl. header)."""

    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        self._font_family = "Helvetica"
        self._font_size_body = 11
        self._font_size_title = 13
        self._font_size_header = 11
        self._unicode_font = False

    def _safe(self, text: str) -> str:
        return _pdf_text_for_font(text, unicode_font=self._unicode_font)

    def header(self) -> None:  # noqa: D401
        self.set_font(self._font_family, "", self._font_size_header)
        self.cell(0, 10, self._safe("SAFe DevOps Self-Assessment (Pilot)"), ln=True)
        self.ln(2)

    def section_title(self, title: str) -> None:
        self.set_font(self._font_family, "B", self._font_size_title)
        self.multi_cell(0, 8, self._safe(title))
        self.ln(1)

    def body_text(self, text: str) -> None:
        self.set_font(self._font_family, "", self._font_size_body)
        self.multi_cell(0, 6, self._safe(text or ""))
        self.ln(2)


def _try_register_dejavu(pdf: ReportPDF, regular: Path, bold: Path) -> bool:
    if not regular.is_file() or not bold.is_file():
        return False
    pdf.add_font("DejaVu", "", str(regular))
    pdf.add_font("DejaVu", "B", str(bold))
    pdf._font_family = "DejaVu"
    pdf._font_size_body = 10
    pdf._font_size_title = 13
    pdf._font_size_header = 10
    pdf._unicode_font = True
    return True


def _ensure_dejavu(pdf: ReportPDF) -> None:
    """Use DejaVu from fpdf wheel, or from backend/fonts/, else Helvetica + Latin-1-safe text."""
    try:
        import fpdf

        pkg_font = Path(fpdf.__file__).resolve().parent / "font"
        if _try_register_dejavu(pdf, pkg_font / "DejaVuSans.ttf", pkg_font / "DejaVuSans-Bold.ttf"):
            pass
        elif _try_register_dejavu(
            pdf, _PROJECT_FONT_DIR / "DejaVuSans.ttf", _PROJECT_FONT_DIR / "DejaVuSans-Bold.ttf"
        ):
            pass
    except (OSError, ImportError, TypeError, ValueError, RuntimeError):
        pdf._font_family = "Helvetica"
        pdf._unicode_font = False
        pdf._font_size_body = 11
        pdf._font_size_title = 13
        pdf._font_size_header = 11
    pdf.set_font(pdf._font_family, "", pdf._font_size_body)


def build_pdf_report(
    definition: AssessmentDefinition,
    session: AssessmentSession,
    responses: dict[str, PracticeResponse],
    results: dict[str, Any],
) -> bytes:
    pdf = ReportPDF()
    _ensure_dejavu(pdf)
    pdf.add_page()

    pdf.section_title("Participant")
    pdf.body_text(
        f"Name: {session.name}\n"
        f"Email: {session.email}\n"
        f"Team: {session.team_name}\n"
        f"Assessment version: {definition.assessment_version}\n"
        f"Generated (UTC): {results['timestamp_utc']}"
    )

    if results.get("partial_export"):
        pdf.section_title("Export status")
        pdf.body_text(
            "PARTIAL / EARLY COMPLETION\n"
            + (results.get("export_summary") or "")
            + f"\nConfirmed practices: {results.get('practices_confirmed_count', 0)} / {results.get('practices_total', 0)} "
            f"({results.get('completion_percentage', 0)}%)."
        )

    pdf.section_title("Domain summaries (quantitative detail in results.json)")
    for area, data in results.get("domain_rollups", {}).items():
        avg = data.get("average_score")
        inc = data.get("practices_incomplete_or_unconfirmed", 0)
        pdf.body_text(
            f"{area}: average score (confirmed only) = {avg if avg is not None else 'n/a'}; "
            f"incomplete in domain: {inc}"
        )

    overall = results.get("overall_score")
    pdf.section_title("Overall")
    pdf.body_text(
        f"Overall average score (confirmed practices only): {overall if overall is not None else 'n/a'}"
    )

    current_area = ""
    for pdef in definition.practices:
        if pdef.pipeline_area_name != current_area:
            current_area = pdef.pipeline_area_name
            pdf.add_page()
            pdf.section_title(current_area)

        row = responses.get(pdef.key)
        pmeta = next((p for p in results.get("practices", []) if p.get("practice_key") == pdef.key), None)
        status = (pmeta or {}).get("practice_completion_status", "incomplete")
        pdf.section_title(pdef.name)
        if status != "completed":
            pdf.body_text("STATUS: INCOMPLETE — practice not confirmed for this export. No score assigned.")
        pdf.body_text("What it evaluates:\n" + (pdef.what_it_evaluates or "").strip())

        narrative = (row.narrative if row else "") or ""
        pdf.body_text("Team narrative:\n" + (narrative.strip() or "(none)"))

        if row:
            try:
                transcript = json.loads(row.follow_up_transcript_json or "[]")
            except json.JSONDecodeError:
                transcript = []
            if transcript:
                lines = ["Follow-up history:"]
                for item in transcript:
                    k = item.get("kind")
                    if k == "ai_followups":
                        qs = item.get("questions") or []
                        lines.append("  AI follow-up questions: " + "; ".join(str(q) for q in qs))
                    elif k == "user_followup_response":
                        lines.append("  Team follow-up response: " + str(item.get("text", "")))
                pdf.body_text("\n".join(lines))

            try:
                files = json.loads(row.files_json or "[]")
            except json.JSONDecodeError:
                files = []
            if files:
                fnames = ", ".join(str(f.get("filename", "")) for f in files)
                pdf.body_text("Evidence files (filenames only; images not embedded in pilot PDF):\n" + fnames)

            try:
                notes = json.loads(row.evidence_notes_json or "[]")
            except json.JSONDecodeError:
                notes = []
            if notes and status == "completed":
                pdf.body_text("Evidence notes (from review):\n" + "\n".join(f"- {n}" for n in notes))
            if status == "completed" and row.rationale_summary:
                pdf.body_text("Score rationale (for reviewer):\n" + (row.rationale_summary or "").strip())

        pdf.ln(2)

    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(raw).encode("latin-1")


def write_export_zip(session_id: int, pdf_bytes: bytes, results: dict[str, Any]) -> Path:
    export_dir = Path(__file__).resolve().parent.parent.parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = export_dir / f"assessment_export_{session_id}_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.pdf", pdf_bytes)
        zf.writestr("results.json", json.dumps(results, indent=2, ensure_ascii=False))
    return zip_path


def load_responses_map(db: Session, session_id: int) -> dict[str, PracticeResponse]:
    rows = db.query(PracticeResponse).filter(PracticeResponse.session_id == session_id).all()
    return {r.practice_key: r for r in rows}
