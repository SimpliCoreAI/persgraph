# Setup Notes — Reference (not loaded in context)

## Google / gog Setup
- Account: `jkjs35149.openclaw@gmail.com`
- Auth configured: 2026-05-23 — gmail, calendar, drive, contacts, docs, sheets
- Gmail API: enable in GCloud console (project 856132602070)
- GOG_ACCOUNT env var: set to above

## Google Drive — File Processing
- Upload folder: `~/Library/CloudStorage/GoogleDrive-jkjs35149.openclaw@gmail.com/My Drive/uploads/input`
- CC ingestion script: `scripts/ingest_cc_rewards.py`

## API Cost Tracking
- Script: `scripts/track_api_cost.py`
- Data: `data/api_costs.json`
- Daily summary (8pm): `scripts/send_cost_summary.sh`

## PersGraph DB Architecture
- Notes/Tasks/Appointments: SQLite — `data/notes.db` via `second_brain/notes_db.py`
- Places: SQLite — `data/places.db` via `second_brain/places_db.py`
- ChromaDB (Windows 100.122.130.89): articles/PDFs/URLs/emails/youtube only

## VPS Architecture
- Local (Mac): raw sensitive files only — CC statements, portfolio PDFs
- VPS: OpenClaw, PersGraph, SQLite, all cron jobs
- Windows (Andromeda): Ollama + ChromaDB via Tailscale
- Tailscale VPS IP: 100.120.84.86

## Tailscale IPs
- VPS (ubuntu-2gb-hil-1): 100.120.84.86
- Windows (andromeda): 100.122.130.89
- MacBook Air: 100.121.8.38
