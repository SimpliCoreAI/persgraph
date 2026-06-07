# Streamlit UI

Interactive dashboard for the PersGraph second brain — Learning Agent, Snippets, Tasks, Places, Finance, and more.

## Run locally (Mac / Linux)

```bash
cd ~/AgenticHub/Persgraph
source .venv/bin/activate
PYTHONPATH=. streamlit run streamlit/app.py
# Open: http://localhost:8501
```

## Run on Windows (access via Tailscale from Mac)

```powershell
pip install streamlit plotly
streamlit run streamlit/app.py --server.address 100.122.130.89 --server.port 8501
```

Access from Mac browser:
```
http://100.122.130.89:8501
```

Firewall rule (run once on Windows as Admin):
```powershell
New-NetFirewallRule -DisplayName "Allow Streamlit Tailscale" `
  -Direction Inbound -Protocol TCP -LocalPort 8501 `
  -RemoteAddress "100.0.0.0/8" -Action Allow
```

## Tabs

| Tab | Feature |
|-----|---------|
| 🎓 Learning Agent | RAG Q&A + ingest from UI |
| 📎 Snippets | Semantic search across knowledge base |
| ✅ Tasks & Notes | CRUD for tasks, notes, appointments |
| 🗺️ Travel & POI | Places graph — search, ratings, map view |
| 🔁 Recurring Events | Cron job manager + cost tracker |
| 💸 Fees & Charges | Interest, late fees, annual fees |
| 💼 Portfolio | Financial analysis *(Phase 2)* |
| 💳 Credit Card Agent | Statement parsing, rewards *(Phase 2)* |
| 📋 Weekly Briefing | Sunday digest *(Phase 2)* |
