# Setup Notes — Private Local Reference

This file intentionally avoids real personal accounts, hostnames, or IPs in the public repo.

## Google / gog Setup
- Account: store in local env/docs outside the repo
- Enable required Google APIs in your own cloud project
- Set `GOG_ACCOUNT` in local environment

## Google Drive — File Processing
- Upload folder: use your local Google Drive path outside the repo
- CC ingestion script: `scripts/ingest_cc_rewards.py`

## API Cost Tracking
- Script: `scripts/track_api_cost.py`
- Data: `data/api_costs.json`
- Daily summary (8pm): `scripts/send_cost_summary.sh`

## PersGraph DB Architecture
- Notes/Tasks/Appointments: SQLite — `data/notes.db` via `second_brain/notes_db.py`
- Places: SQLite — `data/places.db` via `second_brain/places_db.py`
- ChromaDB: configure via env/config for your own host

## Deployment Architecture
- Keep raw sensitive files outside the public repo
- Run OpenClaw/PersGraph on your chosen host
- Configure Ollama + ChromaDB endpoints via env/config

## Host / Network Details
- Store machine names, Tailscale IPs, and account mappings in private notes, not this repo
