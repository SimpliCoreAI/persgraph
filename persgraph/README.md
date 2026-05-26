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

## Part of second-brain
PersGraph is a module inside [second-brain](https://github.com/JollyS/second-brain) — a local-first personal AI assistant.
