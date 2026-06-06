# scripts/AGENTS.md — Scripting Conventions

## Runtime
- Always use the venv: `PYTHONPATH=. .venv/bin/python scripts/<script>.py`
- Entry point for all Telegram commands: `scripts/command.py --sender <id> "<cmd>"`
- Queue worker: `scripts/queue_worker.py` — processes async saves

## Script Patterns
- Each script is standalone — import from `second_brain.*`, not from other scripts
- Use `config.yaml` via `second_brain.config` for all paths/settings
- Never hardcode paths — resolve via config or `pathlib.Path`
- Scripts that write to ChromaDB: confirm chunk count at end

## Cron / Scheduled Scripts
- `check_appointments.py` → runs every 1h via OpenClaw cron (cron id: 497e6162)
- `weekly_briefing.py` → Sunday digest
- `track_api_cost.py` → daily 8pm cost summary
- New cron scripts: add cron id to MEMORY.md after registering

## Error Handling
- All scripts: wrap main logic in try/except, log clearly to stdout
- Failed ingestion: print reason, do NOT silently skip chunks
- Telegram-facing scripts: always return a user-readable message

## Medium / Paywalled URLs
- Replace `https://<domain>/<slug>` → `https://freedium-mirror.cfd/https://<domain>/<slug>`
- Try original first; fall back to freedium on extraction failure
