# SAFe DevOps self-assessment

Open-source (MIT, see `LICENSE`) single-page guided self-assessment: YAML-defined practices, SQLite persistence, optional image/PDF evidence, OpenAI sufficiency review with inline follow-ups (capped at 3), hidden scoring until the final summary, and ZIP export (`report.pdf` + `results.json`). Content is generic (enterprise-context examples); replace prompts and `enterprise_examples` in the YAML with your own organization’s language as needed.

## Prerequisites

- Python 3.11+ (3.12 recommended; 3.14 supported via flexible deps)
- Node.js 20+
- OpenAI API key (required for Review; set in `backend/.env`)

## Quick start

**1. Backend**

```powershell
cd c:\git\SAFeDevOps\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-...
# Optional: SAFEDEVOPS_DEBUG_MODE=true shows AI rationale and “more detail needed” messaging in the UI.
# Omit it or set false for a gentler flow (follow-up questions only, neutral confirmations).
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**2. Frontend** (new terminal)

```powershell
cd c:\git\SAFeDevOps\frontend
npm install
npm run dev
```

**3. Open** `http://localhost:5173`

The API creates `safedevops_pilot.db`, `uploads/`, and `exports/` automatically on first run. Ensure the backend is running on port 8001 before using the frontend (Review and export require it). If port 8001 is in use, another app may be on 8000—use 8001 for this pilot.

## UX: theme, session, and logo

- **Dark mode**: Use the **Dark mode** / **Light mode** control in the header. The choice is stored in **localStorage** under `safedevops_theme` and applied on load (before React mounts) so the flash of the wrong theme is minimized.
- **Session**: The active session id is kept in **sessionStorage** (`safedevops_pilot_session_id`). **New session** clears it and returns to the identity step.
- **Logo**: Place a PNG or SVG in `frontend/public/` (for example `company-logo.svg`) and point the app at it with a Vite env var (see `frontend/.env.example`). The default is `public/logo-placeholder.svg`. Set `VITE_APP_LOGO_URL=` to an empty value to hide the image and show a small text fallback. Optional `VITE_APP_TITLE` overrides the assessment title in the header.

## Finish early / partial export

You can **Finish early** from the header or the bottom action area. A confirmation dialog explains that incomplete practices will be labeled in the export. Confirming calls **`POST /api/sessions/{id}/export-partial`** with `{ "confirm_partial": true }` and downloads the same ZIP shape as the full export.

**Behavior**

- **PDF**: Includes every practice; **incomplete** (unconfirmed) practices are marked explicitly; narrative and evidence filenames appear where present. **Score rationale and evidence-review notes are omitted for incomplete practices** so hidden scoring is not leaked before confirmation.
- **JSON** (`results.json`): Built by `backend/app/export_payload.py`. It includes `completion_mode`, `partial_export`, `completion_percentage`, `practices_confirmed_count`, `practices_total`, `export_summary`, per-practice `practice_completion_status` and `progress_detail`, scores and confidence **only for confirmed** practices (otherwise `null`), domain rollups with completed vs incomplete counts, and `overall_partial` where applicable. **No scores are invented** for unconfirmed practices.

The normal **`POST /api/sessions/{id}/export`** still requires all practices confirmed. **`GET /api/sessions/{id}/summary-json`** returns the same payload shape; use query **`allow_incomplete=true`** to retrieve summary JSON before every practice is confirmed (optional for tooling).

## Admin: editing assessment content

All structure, prompts, rubrics, and thresholds for the pilot live in:

`backend/data/assessment.yaml`

- Reorder or nest content under `pipeline_areas` → `practices`. Each practice may include `enterprise_examples` (illustrative bullets shown in the UI as optional context).  
- Use `|` blocks for long text (multiline friendly).  
- Defaults (`defaults.follow_up_cap`, `sufficiency_confidence_threshold`, `low_confidence_flag_threshold`) apply unless a practice overrides `ai_review`.  
- Rubrics live under `rubrics` and are referenced by `ai_review.rubric_ref`.  
- Review instructions for the model are under `review_prompts` (`sufficiency_system`, `sufficiency_user_template`).

After edits, restart the API process so changes reload (the definition is cached on first load; restart clears cache).

### Optional: split YAML

You can replace `assessment.yaml` with a modular layout later; the loader currently reads a single file path from settings (`ASSESSMENT_YAML` can be added if you extend `settings.py`).

## Pilot behavior notes

- **Identity** (name, email, team) is collected once at the start and stored on the session.  
- **Scores** are not shown during the practice flow; they appear on the final summary and in `results.json` / PDF for **confirmed** practices only.  
- **Follow-ups**: up to `defaults.follow_up_cap` rounds (default 3). After the cap, the user can still continue; exports flag `insufficient_after_cap` / low confidence as applicable.  
- **PDF**: text report only (filenames for evidence, no embedded images in this pilot). Core fonts (Helvetica) only cover Latin‑1; pasted “smart” punctuation (e.g. Word’s non‑breaking hyphen U+2011) is normalized so export does not crash. For full Unicode, drop **DejaVuSans.ttf** and **DejaVuSans-Bold.ttf** into `backend/fonts/` (same names) and the exporter will use them automatically.  
- **Multimodal review**: images are sent to the vision-capable model; PDFs use lightweight text extraction for context plus filenames.

## Production-ish build (optional)

```powershell
cd c:\git\SAFeDevOps\frontend
npm run build
```

Serve `frontend/dist` with any static host and point API calls at your FastAPI deployment (update CORS in `.env`).

## Deploying to Railway

This repo is a **monorepo** (`backend/` Python + `frontend/` Vite). **Railpack** fails at the repo root because there is no single `package.json` or `requirements.txt` there.

**Backend (API) — recommended**

- A root **`Dockerfile`** builds the FastAPI app from `backend/` and runs `uvicorn` on **`PORT`** (Railway injects this).
- **`railway.toml`** sets the builder to Docker, watch paths, and **`/api/health`** for health checks.
- In Railway → your API service → **Variables**, set at least:
  - `OPENAI_API_KEY`
  - `CORS_ORIGINS` — include every origin that will load the SPA (e.g. `https://your-frontend.up.railway.app` or your custom domain). Comma-separated, no spaces unless quoted per your host rules.

**Frontend (static)**

- Build with `VITE_API_BASE_URL` set to your **public API URL** (e.g. `https://your-api.up.railway.app`, no trailing slash), then deploy `frontend/dist` (Railway static site, Cloudflare Pages, etc.). See `frontend/.env.example`.

**Alternative (Railpack only, no Docker)**

- In the service **Settings**, set **Root Directory** to `backend` so Railpack sees `requirements.txt`. Set **Start Command** to:  
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
  (and install deps via Railpack’s default or a custom build command if needed.)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 503 on Review | Set `OPENAI_API_KEY` in `backend/.env` and restart the API |
| CORS errors | Add your origin to `CORS_ORIGINS` in `.env` (default includes localhost:5173) |
| 404 on `/api/*` | Ensure backend is running on port 8001; stop any other app on 8000/8001; Vite proxies `/api` to 8001 |
| Session not found | UI stores `sessionId` in `sessionStorage`; clear site data or click "New session" |
| File upload rejected | Use PNG, JPG, WebP, GIF, or PDF; max 15 MB per file |
| Database/table errors | Delete `backend/safedevops_pilot.db` and restart the API to recreate schema |
| Railway “Error creating build plan with Railpack” | Use the root **Dockerfile** + `railway.toml` in this repo, **or** set service **Root Directory** to `backend` |

## Key files (for review)

| Area | Files |
|------|--------|
| Export payload (full + partial JSON) | `backend/app/export_payload.py` |
| PDF + ZIP writers | `backend/app/services/export_builder.py` |
| API routes (including `export-partial`, `summary-json`) | `backend/app/routers/assessment_routes.py` |
| Practice/session API models | `backend/app/schemas_api.py` |
| Main UI layout & partial export flow | `frontend/src/components/AssessmentApp.tsx`, `PracticePanel.tsx`, `ProgressNav.tsx` |
| Theme + persistence | `frontend/src/theme.ts`, `frontend/src/index.css` |
| Header / logo | `frontend/src/components/AppHeader.tsx`, `frontend/public/logo-placeholder.svg` |
