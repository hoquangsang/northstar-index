# Deployment Guide

This project has two runtime paths:

```text
GitHub Actions daily sync -> Gemini File Search
Render Web Service -> Streamlit demo UI -> Gemini File Search
```

The scheduled sync and the public demo are intentionally separate. The sync job
runs on GitHub runners, while Render hosts the UI that answers questions from
the same Gemini File Search store.

## GitHub Actions

### CI

Workflow:

```text
.github/workflows/ci.yml
```

CI runs on pushes, pull requests, and manual dispatch. It installs dev
dependencies, runs `ruff`, `mypy`, `pytest`, and builds the Docker image.

CI does not need secrets.

### Daily sync

Workflow:

```text
.github/workflows/daily-sync.yml
```

Daily sync runs on a cron schedule and can also be triggered manually from the
Actions tab. It runs:

```bash
python main.py sync --limit 50
```

Required GitHub Secret:

```text
GEMINI_API_KEY
```

Recommended GitHub Secret:

```text
GEMINI_FILE_SEARCH_STORE_NAME
```

Use the same `GEMINI_FILE_SEARCH_STORE_NAME` in GitHub and Render once a stable
store exists. This lets the sync job update the same store that the demo UI
queries.

Optional GitHub Variables:

```text
GEMINI_FILE_SEARCH_STORE_DISPLAY_NAME=Northstar OptiSigns KB
GEMINI_MODEL=gemini-3.1-flash-lite
```

The workflow caches `data/manifest.json` between runs to reduce unnecessary
uploads. The manifest is runtime state and is not committed to git.
Each sync run writes `logs/last_run.json`; the log is runtime state and is not
committed to git.

GitHub Actions does not read Render environment variables. Any value needed by
the scheduled job must be configured in GitHub Secrets or Variables.

## Render

Deploy the public demo as a Render Web Service.

Recommended service settings:

```text
Service type: Web Service
Runtime: Docker
Root directory: repository root
Dockerfile path: Dockerfile
```

Use this start command for the Streamlit demo:

```bash
streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=$PORT
```

Render environment variables:

```text
APP_ENV=production
GEMINI_API_KEY=<your Gemini API key>
GEMINI_FILE_SEARCH_STORE_NAME=<same store name used by daily sync>
GEMINI_MODEL=gemini-3.1-flash-lite
```

`PORT` is provided by Render. The Streamlit command above binds to that port.
FastAPI also supports Render's `PORT` env when it is run as the web service, but
the recommended public demo deploy is Streamlit.

## What is not required

Render Cron Job is not required because GitHub Actions handles daily sync.

Render deploy hook is not required for normal document sync because updated
documents are uploaded to Gemini File Search, not baked into the Render image.

Docker Compose is for local smoke testing only. Render should deploy a single
Web Service from the Dockerfile.

## Demo video checklist

Keep the video short:

1. Open the Streamlit Render URL.
2. Ask: `How do I add a YouTube video to OptiSigns?`
3. Show the answer and source URL.
4. Ask: `Toi can chuan bi gi de dung ung dung canh bao dong dat Nhat Ban?`
5. Choose Vietnamese and show the answer.
6. Ask: `How do I integrate Slack with OptiSigns?`
7. Show that the app returns `not_found` instead of inventing an answer.
