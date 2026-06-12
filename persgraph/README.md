# 📊 PersGraph

> Personal finance analytics dashboard — local, private, beautiful.

## What it does
- Analyzes your bank/credit card CSV exports
- Generates interactive Plotly charts (spending, YoY, portfolio, investments)
- Tax anomaly detection: IRS/FTB payments included in totals, excluded from averages
- 10+ smart recommendations per year
- 5-tab dashboard: 2025 | 2026 YTD | YoY | Portfolio 2025 | Portfolio 2026

## Quick Start
```bash
cd persgraph
./setup.sh
```

## Data
Drop CSV exports into `persgraph/data/`:
- `transactions_2025.csv` — full year 2025
- `transactions_2026.csv` — 2026 YTD

Expected CSV columns: `Date, Account, Description, Category, Tags, Amount`

## Refresh data
1. Drop new CSV into `data/`
2. Click "🔄 Refresh All" in the dashboard
   — or run: `python3 analyze_2025.py` / `analyze_transactions.py` / `analyze_yoy.py`

## Architecture
- `analyze_*.py` — data processing + Plotly HTML generation
- `serve.py` — local HTTP server (port 8765) with /api/refresh endpoint
- `dashboard.html` — 5-tab UI with live refresh
- `data/` — gitignored (your private CSVs stay local)

## Part of PersGraph
PersGraph is a local-first personal data graph — knowledge, finance, places, tasks. All on your machine. See the [main repo](https://github.com/SimpliCoreAI/persgraph).


## Everyday Commands

PersGraph is becoming more than a dashboard — it is a personal command layer.

- `/ask` — ask questions across your saved knowledge
- `/ingest` — save articles and links
- `/place` — remember places worth revisiting
- `/appointment` — store important appointments
- `/schedule` — see what is coming up
- `/sport` — sports status command path is ready for provider config
