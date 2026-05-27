# 📊 PersGraph

**Private, local-first personal data graph — knowledge, finance, places, tasks. All on your machine.**

No subscriptions. No cloud. Your data stays yours.

---

## Architecture

```
┌─────────────────────────────────┐     Tailscale VPN
│  Mac (OpenClaw)                 │◄──────────────────►│  Windows (96GB RAM)        │
│  · Orchestration & agents       │                     │  · Ollama (Qwen2.5:7b)     │
│  · Claude for reasoning         │                     │  · ChromaDB vector store   │
│  · Telegram interface           │                     │  · All embeddings & LLM    │
│  · Cron jobs & automation       │                     │                            │
│  · Image scanning (vision AI)   │                     │                            │
└─────────────────────────────────┘                     └────────────────────────────┘
```

Nothing leaves your local network (except Claude API calls for agent orchestration).
Incoming Telegram images are scanned with a vision model and auto-saved to the Obsidian vault.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Orchestration | OpenClaw (agent runtime) |
| LLM Reasoning | Anthropic Claude (Sonnet) |
| Local LLM + Embeddings | Ollama (Qwen2.5, nomic-embed-text) |
| Vector Store | ChromaDB |
| Knowledge Base | Obsidian vault |
| RAG Pipeline | Custom Python + ChromaDB |
| Networking | Tailscale VPN |
| Interface | Telegram Bot |
| Tool Protocol | MCP (Model Context Protocol) |
| Ingest Formats | PDF, URL, Markdown, Email, Images |

---

## What's Working

| Feature | Status |
|---|---|
| PDF ingestion → ChromaDB | ✅ Working |
| URL / web ingestion | ✅ Working |
| RAG Q&A (Qwen2.5:7b via Ollama) | ✅ Working |
| Tasks, Notes, Appointments (ChromaDB) | ✅ Working |
| Appointment reminders (cron, 8am daily) | ✅ Live |
| API cost tracking (cron, 8pm daily) | ✅ Live |
| Recurring Events manager | ✅ Working |
| Travel & POI (places graph) | ✅ Working |
| Snippets — semantic search | ✅ Working |
| Learning Agent (RAG Q&A from UI) | ✅ Working |
| Fees & Charges (SQLite-powered) | ✅ Working |
| Streamlit dashboard (9 tabs) | ✅ Live |
| Telegram Image Scanning → Obsidian → ChromaDB | ✅ Working |
| Portfolio / financial analysis | 🔲 Phase 2 |
| Credit Card Agent | 🔲 Phase 2 |
| Weekly Briefing Agent | 🔲 Phase 2 |
| YouTube ingester | 🔲 Phase 2 |

---

## Setup

```bash
git clone https://github.com/JollyS/persgraph.git ~/AgenticHub/Persgraph
cd ~/AgenticHub/Persgraph
bash setup.sh
```

`setup.sh` handles everything: venv, dependencies, `.env` creation, Ollama model pull, ChromaDB check, and OpenClaw/gog verification.

**Full step-by-step guide:** → [`INSTALL.md`](INSTALL.md)
**OpenClaw agent setup:** → [`OPENCLAW_SETUP.md`](OPENCLAW_SETUP.md)

### Services (Ollama + ChromaDB)

**Option A — Docker (no extra installs):**
```bash
docker compose up -d
```

**Option B — Native Ollama:**
```bash
ollama serve
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

**Option C — Remote machine via Tailscale:**
```env
# In .env:
OLLAMA_BASE_URL=http://<tailscale-ip>:11434
CHROMA_HOST=<tailscale-ip>
```

---

## Usage

### Ingest documents
```bash
# PDF
PYTHONPATH=. python scripts/ingest.py pdf ~/Documents/notes.pdf --tag research

# URL / web article
PYTHONPATH=. python scripts/ingest.py url https://example.com/article --tag ai
```

### Ask your knowledge base
```bash
PYTHONPATH=. python scripts/query.py "What are my notes on RAG vs fine-tuning?"
```

### Slash commands (via Telegram or terminal)
```bash
PYTHONPATH=. python scripts/command.py "<command>"
```

| Command | Description |
|---|---|
| `/ingest <url or file>` | Ingest a URL, PDF, or web article |
| `/ask <question>` | RAG query + AI synthesis from saved content |
| `/note <text>` | Save a quick note |
| `/task <text>` | Save a task or appointment |
| `/place <name> in <city>` | Save a place to your POI graph |
| `/wiki-ingest <url>` | Ingest a Wikipedia article as a structured note |
| `/summarize <url>` | Summarize a page without ingesting |
| `/quiz <topic>` | Generate Q&A flashcards from saved content *(coming soon)* |
| `/status` | System status (Ollama, ChromaDB, note count) |

### Check appointments
```bash
PYTHONPATH=. python scripts/check_appointments.py
# Returns any appointments within the next 48 hours
```

---

## Streamlit Dashboard Tabs

| Tab | Feature | Status |
|---|---|---|
| 🎓 Learning Agent | RAG Q&A + ingest from UI | ✅ |
| 📎 Snippets | Semantic search across knowledge base | ✅ |
| ✅ Tasks & Notes | CRUD for tasks, notes, appointments | ✅ |
| 💼 Portfolio | Financial analysis & charts | 🔲 Phase 2 |
| 💳 Credit Card Agent | Statement parsing, rewards tracking | 🔲 Phase 2 |
| 🗺️ Travel & POI | Places graph — search, ratings, map view | ✅ |
| 📋 Weekly Briefing | Automated Sunday digest | 🔲 Phase 2 |
| 🔁 Recurring Events | Cron job manager + cost tracker | ✅ |
| 💸 Fees & Charges | Interest, late fees, annual fees (SQLite) | ✅ |

---

## Cron Jobs

| Job | Schedule | What it does |
|---|---|---|
| `appointment-reminder` | 8:00 AM daily | Scans ChromaDB → Telegram alert if appointment within 48h |
| `api-cost-tracking` | 8:00 PM daily | Logs token usage → Telegram daily cost summary |

---

## Project Structure

```
persgraph/
├── README.md
├── .env                          # Local config (gitignored)
├── .env.example                  # Config template
├── requirements.txt
├── pyproject.toml
├── architecture.md               # Full system design
├── second_brain/                 # Core Python package
│   ├── config.py                 # Settings (pydantic-settings + .env)
│   ├── embeddings.py             # Ollama embedding client
│   ├── vectorstore.py            # ChromaDB wrapper
│   ├── query.py                  # RAG query engine
│   ├── notes.py                  # Tasks/Notes CRUD
│   ├── places.py                 # Travel & POI CRUD
│   └── ingesters/
│       ├── pdf.py
│       └── url.py
├── db/                           # SQLite layer (fees, transactions)
│   ├── schema.sql
│   ├── queries.py
│   └── ingest.py
├── persgraph/                    # Standalone HTML dashboards
│   ├── analyze_transactions.py
│   ├── analyze_yoy.py
│   ├── fees_chart.py
│   ├── dashboard.html
│   └── run_dashboard.sh
├── scripts/
│   ├── ingest.py                 # Ingest CLI
│   ├── query.py                  # Query CLI
│   ├── command.py                # Slash command handler
│   ├── check_appointments.py    # Appointment checker (cron)
│   └── track_api_cost.py        # API cost logger (cron)
├── streamlit/
│   ├── app.py                    # Home + sidebar nav
│   └── pages/
│       ├── 1_learning_agent.py
│       ├── 2_snippets.py
│       ├── 3_tasks_notes.py
│       ├── 4_portfolio.py
│       ├── 5_credit_card.py
│       ├── 6_travel.py
│       ├── 7_weekly_briefing.py
│       ├── 8_recurring_events.py
│       └── 9_fees.py
└── marketing/
    └── persgraph-landing.html
```

---

## License

MIT — use it, fork it, make it yours.
