# 🧠 Second Brain

A private, local-first AI system for your personal knowledge — PDFs, notes, emails, URLs, YouTube transcripts, and financial documents.

**Architecture:**
- 🖥️ **Mac (OpenClaw):** Orchestration, ingestion scripts, Claude for reasoning, Telegram interface
- 🖥️ **Windows (96GB RAM):** Ollama (embeddings + LLM) + ChromaDB — all via Tailscale

Nothing leaves your local network (except Claude API calls for orchestration).

---

## What's Built

| Feature | Status |
|---|---|
| PDF ingester | ✅ Working |
| URL ingester | ✅ Working |
| RAG query (Qwen2.5:7b) | ✅ Working |
| Tasks & Notes (ChromaDB) | ✅ Working |
| Streamlit dashboard (8 tabs) | ✅ Scaffolded |
| Learning Agent tab | ✅ Fully wired |
| Snippets tab | ✅ Fully wired |
| Appointment reminders (cron) | ✅ Live — 8am daily |
| API cost tracking (cron) | ✅ Live — 8pm daily |
| Recurring Events tab | ✅ Working |
| Credit Card Agent | 🔲 In progress |
| Travel & POI | 🔲 Planned |
| Portfolio tab | 🔲 Planned |
| Weekly Briefing Agent | 🔲 Planned |
| YouTube ingester | 🔲 Planned |

---

## Setup

### 1. Clone
```bash
git clone https://github.com/JollyS/second-brain.git
cd second-brain
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — set WINDOWS_IP to your Tailscale IP
```

### 4. Verify Windows connectivity
```bash
curl http://<tailscale-ip>:11434/api/tags        # Ollama
curl http://<tailscale-ip>:8000/api/v1/heartbeat # ChromaDB
```

---

## Usage

### Ingest documents
```bash
PYTHONPATH=. python3 scripts/ingest.py pdf ~/Documents/portfolio.pdf --tag financial
PYTHONPATH=. python3 scripts/ingest.py url https://example.com/article --tag research
```

### Query your brain
```bash
PYTHONPATH=. python3 scripts/query.py "What are my portfolio returns for 2025?"
```

### Launch Streamlit dashboard
```bash
PYTHONPATH=. streamlit run streamlit/app.py
# Access at http://localhost:8501
```

---

## Project Structure

```
second-brain/
├── .env                          # Local config (gitignored)
├── .env.example                  # Config template
├── requirements.txt              # Python deps
├── pyproject.toml                # Package config
├── architecture.md               # Full system design doc
├── data/
│   └── api_costs.json            # Daily API cost log
├── second_brain/                 # Core package
│   ├── config.py                 # Settings (pydantic-settings + .env)
│   ├── embeddings.py             # Ollama embedding client
│   ├── vectorstore.py            # ChromaDB wrapper
│   ├── query.py                  # RAG query engine
│   ├── notes.py                  # Tasks/Notes CRUD
│   └── ingesters/
│       ├── base.py               # Abstract base ingester
│       ├── pdf.py                # PDF ingester
│       └── url.py                # URL ingester
├── scripts/
│   ├── ingest.py                 # Ingest CLI (typer)
│   ├── query.py                  # Query CLI (typer)
│   ├── check_appointments.py     # Appointment checker (cron)
│   └── track_api_cost.py         # API cost logger (cron)
└── streamlit/
    ├── app.py                    # Home + sidebar nav
    └── pages/
        ├── 1_learning_agent.py   # RAG Q&A + ingest
        ├── 2_snippets.py         # Semantic search
        ├── 3_tasks_notes.py      # Tasks/Notes CRUD
        ├── 4_portfolio.py        # Financial docs (scaffold)
        ├── 5_credit_card.py      # CC Agent (scaffold)
        ├── 6_travel.py           # Travel & POI (scaffold)
        ├── 7_weekly_briefing.py  # Weekly digest (scaffold)
        └── 8_recurring_events.py # Cron jobs + cost tracker
```

---

## Cron Jobs (OpenClaw)

| Job | Schedule | Action |
|---|---|---|
| `appointment-reminder` | 8:00 AM daily | Check ChromaDB → Telegram alert if appointment within 48h |
| `daily-api-cost` | 8:00 PM daily | Log token usage → Telegram cost summary |
| `weekly-briefing` | Sunday 8:00 AM | Full digest → Telegram + Email *(planned)* |
