# 🧠 Second Brain — Project Overview

> A private, local-first AI system for personal knowledge, finance, and life management.

---

## What Is It?

Second Brain is a distributed personal AI assistant that lives on your own machines — no data sent to cloud services except for Claude API orchestration. It ingests your documents, notes, and web content, makes them semantically searchable, and answers questions using local LLMs.

Think of it as your personal ChatGPT — but with your own data, running on your own hardware, with zero privacy trade-offs.

---

## Architecture

```
You (Telegram / Browser)
        │
        ▼
┌─────────────────────────┐
│  Mac — Orchestration    │
│  OpenClaw + Claude API  │
│  Ingestion scripts      │
│  Streamlit dashboard    │
└────────────┬────────────┘
             │ Tailscale VPN (encrypted)
             ▼
┌─────────────────────────┐
│  Windows — Compute      │
│  Ollama (Qwen2.5:72b)   │
│  nomic-embed-text       │
│  ChromaDB vector store  │
└─────────────────────────┘
```

**Mac** = brain (orchestration, routing, UI)
**Windows (96GB RAM)** = muscle (LLM inference, embeddings, vector storage)
**Everything connected via Tailscale VPN** — encrypted, zero open ports

---

## Key Features

### ✅ Built
| Feature | Description |
|---|---|
| PDF ingestion | Extract, chunk, embed, store any PDF |
| URL ingestion | Scrape and ingest any web page |
| RAG Q&A | Ask questions over your knowledge base |
| Tasks & Notes | Capture and semantically search notes/tasks/appointments |
| Travel & POI | Save places with auto-tagging, bar charts by country/city/category |
| Appointment reminders | Daily 8am Telegram alert for upcoming appointments |
| API cost tracking | Daily 8pm Telegram summary of Claude API spend |
| Async save queue | Queue saves from Telegram, worker processes in background |
| Streamlit dashboard | 8-tab local web UI |

### 🔲 In Progress
| Feature | Description |
|---|---|
| Credit Card Agent | Statement parsing, rewards optimization via Koko Finance MCP |
| Portfolio analysis | Financial document analysis + Plotly charts |
| Weekly Briefing | Sunday digest via Telegram + Email |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Orchestration | OpenClaw + Claude Sonnet 4.6 |
| Local LLM | Ollama + Qwen2.5:72b / 7b |
| Embeddings | nomic-embed-text (local) |
| Vector store | ChromaDB (local, Windows) |
| Dashboard | Streamlit |
| Charts | Plotly |
| Connectivity | Tailscale VPN |
| Version control | GitHub (private) |
| External storage | Google Drive (sensitive files only) |
| Language | Python 3.9+ |

---

## Privacy Model

- ✅ All embeddings and LLM inference run locally on Windows
- ✅ ChromaDB runs locally — no data leaves your network
- ✅ Sensitive files (CC statements, portfolio) stored in Google Drive, never in git
- ✅ Only Claude API calls leave the machine (orchestration only)
- ✅ Tailscale VPN — no open ports, no router exposure

---

## Credit Card Agent (Next)

Using **Koko Finance MCP Server** — no API key needed, covers 100+ US cards:

| Tool | What it does |
|---|---|
| `which_card_at_merchant` | "I'm at Costco — which card?" |
| `recommend_card_for_category` | Best card for dining/travel/groceries |
| `optimize_portfolio` | Portfolio health score, keep/cancel verdicts |
| `compare_cards` | Side-by-side comparison |
| `check_merchant_benefits` | Card credits at specific merchants |

Combined with your own statement parsing (local, private) for spend analysis.

---

## Multi-Agent Roadmap (Phase 2)

```
OpenClaw (orchestrator)
    ├── Claude Code harness    → complex coding, analysis
    ├── RAG Agent              → ChromaDB retrieval
    ├── Parser Agent           → document extraction
    ├── CC Agent               → Koko MCP + statement parsing
    └── Briefing Agent         → weekly digest generation
```

---

## Repo

**GitHub:** `github.com/JollyS/persgraph` (private)

```
persgraph/
├── second_brain/          # Core Python package
│   ├── config.py          # Settings (pydantic-settings)
│   ├── embeddings.py      # Ollama client
│   ├── vectorstore.py     # ChromaDB wrapper
│   ├── query.py           # RAG engine
│   ├── notes.py           # Tasks/Notes CRUD
│   ├── places.py          # Travel & POI
│   ├── queue.py           # Async save queue
│   └── ingesters/         # PDF, URL ingesters
├── scripts/               # CLI tools + cron scripts
├── streamlit/             # Dashboard (8 tabs)
├── data/                  # Local data (gitignored sensitive files)
├── config.yaml            # Paths, models, settings
└── .env                   # Secrets (never committed)
```
