# arbitrInsights

Strategic intelligence dashboard for the **NotVerify / Straker.AI** platform — AI-powered enterprise localization QA (agent orchestration, trust scoring, "Glass Box" explainability, compliance).

A set of scheduled agents produce daily and weekly market-intelligence scans (competitors, regulation, research, events). The results are written to `data/dashboard/*.json` and rendered by a single-page dashboard.

## Live dashboard

Published via GitHub Pages: open `dashboard.html` at the Pages URL.

The hosted version is **read-only** — it renders the latest published JSON snapshots. The interactive "Run task" / "Analyze" buttons require the local Python backend (see below) and are inactive on the static site.

## Running locally (full, interactive)

```bash
cp .env.example .env   # add your ANTHROPIC_API_KEY (and optional GITHUB_TOKEN)
python -m conductor.serve
# opens http://localhost:8080/dashboard.html
```

## What's in the repo

- `dashboard.html` / `index.html` — the dashboard UI (index redirects to the dashboard).
- `conductor/` — local server and agent dispatch.
- `tools/` — API and scheduler helpers.
- `data/dashboard/*.json` — published intelligence snapshots.

## Not published

Personal/operational data is intentionally excluded from this repo (see `.gitignore`):
Gmail / Google Chat / ClickUp digests, reminders, server logs, and `.env` secrets.
