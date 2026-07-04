# Northstar Index

OptiSigns Help Center RAG pipeline with Gemini File Search.

```text
Zendesk articles -> clean Markdown -> manifest delta -> Gemini File Search -> grounded answers
```

The project can scrape public OptiSigns support articles, convert them to
Markdown, track local changes, upload changed documents to Gemini File Search,
and answer questions with verified article citations.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
```

Set `GEMINI_API_KEY` in `.env` before running Gemini upload or ask operations.
Local dry-run ingestion does not require a Gemini key.

## Core Commands

```powershell
python main.py --help
python main.py stats
python main.py sync --limit 50 --dry-run
python main.py sync --limit 50 --local-only
python main.py sync --limit 50
python main.py ask "How do I add a YouTube video?"
python main.py ask "Lam sao them YouTube?" --language vi
python main.py serve
```

`sync` runs the knowledge-base pipeline. It fetches Zendesk articles, writes
Markdown files, updates `data/manifest.json`, and uploads added or changed
documents to Gemini File Search unless `--dry-run` or `--local-only` is used.
Each run writes `logs/last_run.json` for lightweight run auditing.

`ask` is docs-only. It returns `not_found` instead of falling back to Gemini
general knowledge when File Search does not provide a verified citation.
Language defaults to `auto` and can be forced with `--language en` or
`--language vi`.

## Streamlit Demo

Run the lightweight question-answering UI:

```powershell
streamlit run streamlit_app.py
```

The Streamlit app is only a demo wrapper. It calls the same service layer as the
CLI/API and does not contain separate RAG logic.

For the public demo, deploy the Streamlit app on Render with Docker. See
[docs/deployment.md](docs/deployment.md) for the exact Render and GitHub
configuration.

## API

Start FastAPI:

```powershell
python main.py serve
```

Endpoints:

```text
GET  /health
GET  /stats
POST /sync
POST /ask
```

Example `/ask` request:

```json
{
  "question": "How do I add a YouTube video?",
  "language": "auto"
}
```

## Project Structure

```text
app/api/           FastAPI app and routes
app/services/      use-case layer for sync, chat, and stats
app/ingestion/     Zendesk scrape, HTML clean, Markdown write, manifest, pipeline
app/rag/           prompts, retrieval, and Gemini File Search behavior
app/integrations/  external SDK clients
app/utils/         paths, hashing, logging
streamlit_app.py   single-page demo UI
```

## Quality

```powershell
python -m ruff check .
python -m mypy app
python -m pytest
```

CI runs these checks and a Docker build in GitHub Actions.

## Scheduled Sync

Daily knowledge-base sync runs in GitHub Actions:

```text
.github/workflows/daily-sync.yml
```

The sync job fetches Zendesk articles and updates Gemini File Search. The
Render demo reads from that same Gemini store, so a Render deploy hook is not
needed for normal document updates.

## Docker

API service:

```powershell
docker build -t northstar-index .
docker run --rm -p 8000:8000 --env-file .env northstar-index
```

Compose services:

```powershell
docker compose up app
docker compose up ui
```

The API listens on `http://localhost:8000`; the Streamlit demo listens on
`http://localhost:8501`.

## Final Test Guide

Use [docs/final-question-test.md](docs/final-question-test.md) for the manual
RAG smoke test checklist.

Use [docs/deployment.md](docs/deployment.md) for CI, daily sync, Render deploy,
and demo video notes.

## Known Limitations

- No chat history.
- No streaming responses.
- No custom chunking yet; Gemini File Search auto chunking is used.
- Live Gemini upload and ask operations require a valid API key and quota.
