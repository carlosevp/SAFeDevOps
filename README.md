# SAFe DevOps Self-Assessment

A guided, web-based maturity self-assessment aligned with **SAFe** and **DevOps** delivery practices. Teams move through YAML-defined practices in pipeline areas, capture narrative responses and optional evidence (images and PDFs), and use an **AI-assisted sufficiency review** to refine answers before confirmation. Numeric scores stay **hidden until the final summary** or export, so the flow emphasizes honest reflection rather than score-chasing.

[![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-light.svg)](https://sonarcloud.io/summary/new_code?id=carlosevp_SAFeDevOps) [![Snyk Security](https://snyk.io/test/github/carlosevp/SAFeDevOps/badge.svg)](https://snyk.io/test/github/carlosevp/SAFeDevOps)

**License:** [MIT](LICENSE)

---

## Goals

- **Structured assessment** — Practices, prompts, rubrics, and thresholds live in configuration (`backend/data/assessment.yaml`), not code, so content owners can adapt language and scope without redeploying logic.
- **Quality of input** — OpenAI reviews narrative sufficiency, proposes short follow-up questions, and respects a configurable follow-up cap before allowing a controlled proceed-with-flags path.
- **Audit-ready outputs** — Confirmed sessions can export a ZIP containing a **PDF report** and **`results.json`** with scores, rollups, and completion metadata; partial export is supported when the assessment is finished early.
- **Single deployment surface** — Production can be one container: static SPA and API share one origin (simpler CORS and cookies).

---

## What’s included

| Capability | Description |
|------------|-------------|
| **Practice flow** | Identity capture, ordered practices, draft save, file uploads (PNG, JPEG, WebP, GIF, PDF; 15 MB per file). |
| **AI review** | Sufficiency check, follow-up rounds (default cap: 3), multimodal context for images and PDF text excerpts. |
| **Scoring discipline** | Scores and detailed rationale for scoring appear only for **confirmed** practices in summary and export. |
| **Theming** | Light/dark mode; optional logo and title via Vite environment variables. |
| **Access control (optional)** | Shared password gate with signed **HttpOnly** cookie for demos or constrained environments. |

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Browser    │────▶│  FastAPI (API)   │────▶│  SQLite     │
│  (React/Vite)     │  + embedded SPA  │     │  + uploads  │
└─────────────┘     └────────┬─────────┘     └─────────────┘
                              │
                              ▼
                       OpenAI (chat + vision)
```

- **Frontend:** React 18, TypeScript, Vite (`frontend/`).
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Uvicorn (`backend/`).
- **Data:** SQLite by default; files under `uploads/`; exports under `exports/`.
- **Container:** Multi-stage **Dockerfile** — Node builds the SPA, Python serves API + static `spa_dist` on `PORT`.

---

## Prerequisites

- **Python** 3.11+ (3.12 recommended)
- **Node.js** 20+
- **OpenAI API key** (required for “Review this response” and follow-ups)

---

## Local development

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set OPENAI_API_KEY and adjust options as needed.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, then:
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

On first run the API creates `safedevops_pilot.db`, `uploads/`, and `exports/` under the backend working directory.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies API calls to the backend (default: port **8001**).

### 3. Production-style frontend build (optional)

```powershell
cd frontend
npm run build
```

The output is `frontend/dist/`. For a split deployment, host that directory as static files and point the app at your API with `VITE_API_BASE_URL` (see `frontend/.env.example`).

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | **Required** for review and follow-up calls. |
| `OPENAI_MODEL` | Model id (default `gpt-4o`). |
| `OPENAI_TIMEOUT_SECONDS` | Client timeout for OpenAI requests (default `120`). |
| `CORS_ORIGINS` | Comma-separated browser origins when the SPA is **not** same-origin as the API. |
| `SAFEDEVOPS_DEBUG_MODE` | When `true`, exposes more AI-facing messaging in the UI; omit or `false` for a neutral participant experience. |
| `SAFEDEVOPS_ACCESS_PASSWORD` | When set, requires a shared password before SPA and `/api` (health and gate routes stay public). |
| `DATABASE_URL` | Optional; default SQLite file in the backend directory. |

Full examples: `backend/.env.example`, `frontend/.env.example`.

---

## Docker

Build and run the **combined** image (API + built SPA):

```bash
docker build -t safedevops-assessment .
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e OPENAI_API_KEY=sk-... \
  safedevops-assessment
```

Then open **http://localhost:8080**. Same-origin `/api` is used automatically when `VITE_API_BASE_URL` is unset at build time.

To build for an API hosted on a **different** origin:

```bash
docker build --build-arg VITE_API_BASE_URL=https://api.example.com -t safedevops-assessment .
```

---

## Deployment

### Recommended: one container (same host for UI and API)

1. Build the image from the **repository root** using the provided `Dockerfile`.
2. Run with **`PORT`** set by your platform (e.g. PaaS injects it automatically).
3. Set **`OPENAI_API_KEY`** in the environment.
4. If the browser origin differs from the API, set **`CORS_ORIGINS`** accordingly.
5. Optional: **`SAFEDEVOPS_ACCESS_PASSWORD`** for a simple shared gate.

**Health check:** `GET /api/health`

This repository includes **`railway.toml`** wired to the root Dockerfile and the health path above; equivalent settings apply on other container hosts.

### Alternative: API only (Railpack / Python root)

Point the service **root directory** at `backend`, install from `requirements.txt`, and start:

`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

You must host the SPA separately and set **`VITE_API_BASE_URL`** plus **`CORS_ORIGINS`** on the API.

---

## Customizing assessment content

- **Primary file:** `backend/data/assessment.yaml` — pipeline areas, practices, prompts, `enterprise_examples`, rubrics, defaults (`follow_up_cap`, `sufficiency_confidence_threshold`, etc.), and `review_prompts` (`sufficiency_system`, `sufficiency_user_template`).
- After editing YAML, **restart the API** so the cached definition reloads.

For Unicode-heavy PDFs beyond basic Latin-1, place **DejaVuSans.ttf** and **DejaVuSans-Bold.ttf** in `backend/fonts/` (exact filenames) for embedded font support in exports.

---

## Participant experience (summary)

- **Identity** (name, email, team) is stored on the session.
- **Scores** appear on the final summary and in exports for **confirmed** practices only.
- **Finish early / partial export** labels incomplete practices explicitly and avoids leaking hidden scoring for unconfirmed items in PDF/JSON.
- **Theme** preference: `localStorage`. **Session id:** `sessionStorage` (use “New session” or clear site data to reset).

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| Review returns service / gateway errors | Confirm `OPENAI_API_KEY` and `OPENAI_MODEL`; check platform timeouts for long requests; reduce large attachments. |
| CORS errors in the browser | Add the SPA origin to `CORS_ORIGINS`. |
| API 404 from Vite dev | Ensure the backend is on **8001** and the dev proxy matches (or adjust ports consistently). |
| Upload rejected | Allowed types: PNG, JPEG, WebP, GIF, PDF; max **15 MB** per file. |
| Schema / DB issues after upgrades | Stop the API, remove the SQLite file if appropriate, restart to recreate tables (destroys local data). |
| Monorepo build fails on a PaaS “auto detect” | Use the **root Dockerfile** or set root to `backend` and host the SPA separately. |

---

## Contributing

Issues and pull requests are welcome. Keep changes focused; match existing style and avoid committing secrets (never commit `.env`).
