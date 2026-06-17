# 📊 PersGraph

**Your personal data, graphed & queryable — local-first, private, AI-powered.**

> PersGraph ingests everything about you — emails, notes, tasks, finance, travel — and makes it all semantically searchable with AI. Your data, your graph, your machine.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://python.org)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20local-green?style=flat-square)](https://ollama.ai)
[![ChromaDB](https://img.shields.io/badge/Vector-ChromaDB-orange?style=flat-square)](https://trychroma.com)
[![Claude](https://img.shields.io/badge/Reasoning-Claude%20Sonnet-violet?style=flat-square)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## Why PersGraph?

Most "personal AI" tools ship your data to a cloud. Your emails, your notes, your finances — all processed on someone else's servers, feeding someone else's models.

PersGraph takes the opposite position:

- **LLMs run locally** via Ollama — your data never touches an external embedding API
- **Vector search is self-hosted** — ChromaDB runs on your machine or homelab
- **You own the code** — MIT licensed, inspect every line, no black boxes
- **Air-gap ready** — works fully offline once models are pulled

Claude Sonnet is used only for agent reasoning (orchestration decisions, synthesis) — not for embedding or storing your personal data.

---

## What It Does

PersGraph turns messy personal data into a clean command interface you can actually use every day.

It is built on OpenClaw, an open-source self-hosted agent runtime, with custom skills for personal data orchestration, RAG, and life automation.

### Current slash commands

- `/pghelp` — PersGraph-specific command guide for Telegram/chat use
- `/ingest <url or file>` — raw URL/file ingest into the semantic search layer
- `/wiki-ingest <url>` — write a curated Obsidian wiki note first, then index it
- `/ask <question>` — semantic search + answer synthesis
- `/note <text>` — quick SQLite note capture
- `/task <text>` — quick task capture
- `/place <name>` — save a place
- `/places [query]` — list or search saved places
- `/bucketlist ...` — save or list bucket list places
- `/digest [today|week]` — on-demand summary report
- `/email <message>` — email workflow
- `/appointment <title>, <date/time>` — save or list appointments
- `/schedule [range]` — show your agenda
- `/debrief` — run the debrief flow
- `/status` — collection + queue stats
- `/status service` — PersGraph service/runtime health, route checks, recent logs
- `/status ops` — smoke test, Caddy validity, git/deploy posture

### Public web entry

- Public landing page: `https://persgraph.simplicore.ai/`
- Login page: `https://persgraph.simplicore.ai/login`
- Protected app routes redirect to `/login` when not authenticated
- PersGraph runs behind **Caddy** and the app service `persgraph-web.service` on port `8766`

### Example flow

```
→ /pghelp
🧭 PersGraph command guide

→ /ask what are my upcoming appointments this week?
📅 Found 3 appointments in the next 7 days:
   · Dentist — Mon Jun 2, 10:00 AM           [calendar]
   · Team sync — Wed Jun 4, 2:00 PM          [calendar] [email]
   · Flight YVR → SFO — Fri Jun 6, 7:45 AM  [travel]

→ /place Fujiya Camera, Tokyo
✅ Saved place: Fujiya Camera — Tokyo

→ /appointment Dentist, Jun 20, 2pm
✅ Appointment saved!
📅 Dentist — Jun 20, 2:00 PM PDT

→ /schedule week
📅 Schedule — Next 7 days
   · Jun 20, 2:00 PM PDT — Dentist [Appointment]
```

---

## Features

### 🔍 Semantic Search Across Everything
Vector embeddings on all your data mean you query by meaning, not keywords. Ask about a trip you half-remember, an email you can't find, or a decision you made months ago — PersGraph finds it.

### 📊 Personal Finance Graph
Track hidden fees, interest charges, and late fees across all accounts — powered by SQLite. Statement parsing and CC rewards tracking in Phase 2.

### 📧 Email Ingestion
Trusted sender filtering, intent classification, auto-routing to tasks, appointments, or notes. Zero noise.

### ✅ Tasks & Appointments
Captured from email, Telegram messages, or directly. Reminded before it's too late via daily cron + Telegram alert.

### 🌅 Morning Briefing
Every morning at 8am PST, Gru delivers a personalized briefing to Telegram: top headlines (tech, world, finance), open tasks due today, upcoming appointments within 24 hours, plus the most useful fresh signals from your prebrief when available.

The live Morning Brief runs from an OpenClaw cron job, not a repo script:
- Cron id: `dd967dec`
- Schedule: `0 8 * * *` in `America/Los_Angeles`
- Delivery: isolated agent turn → Telegram
- Handoff: the cron prompt first runs `scripts/run_prebrief.py`, then weaves in fresh `data/prebrief_context.json` context if present

### 🗺 Explore Mode
Explore Mode now sends location-aware nearby suggestions to Telegram when enabled.
- Telegram toggle: `/TripToggle ON`
- Cadence: hourly by default
- Suggestions: nearby POIs with rating/vibe context and Google Maps links when available
- Learning loop: events and outcomes are recorded in a lightweight SQLite learning DB so the system can improve over time
- State sync: the live toggle and persisted checker now share the same source of truth, so cron checks and Telegram delivery stay aligned

### 🕗 Calendar + Email Prebrief
PersGraph includes a prebrief layer that generates a daily context pack from your calendar and inbox. It now acts as a supporting input to the daily Morning Brief while staying safe to run independently. Run `scripts/run_prebrief.py` to generate:

**Machine-readable output** (`data/prebrief_context.json`):
- Today's events and upcoming appointments (next 7 days)
- Bills and payments due soon (ranked by urgency)
- Follow-ups needing action (ranked by urgency)
- Worth-checking emails (new info, invitations, articles)
- Older items to carry forward
- Suggested daily priorities

**Human-readable output** (`data/prebrief_context.md`):
- Daily briefing markdown with emojis and formatting
- Sections with urgency indicators
- Easy to scan and share

**Usage:**
```bash
# Dry-run (synthetic fixtures, offline)
python scripts/run_prebrief.py --dry-run

# Dry-run calendar only
python scripts/run_prebrief.py --dry-run --sources calendar

# Live run (requires Gmail/Yahoo config in .env)
python scripts/run_prebrief.py --sources calendar,gmail,yahoo

# Quiet mode for scheduled handoff into Morning Brief
python scripts/run_prebrief.py --output-dir data --quiet
```

**Configuration:** Set credentials in `.env.local` (gitignored):
```
GMAIL_IMAP_USERNAME=your-gmail@example.com
GMAIL_IMAP_APP_PASSWORD=your-gmail-app-password
YAHOO_IMAP_USERNAME=your-yahoo@example.com
YAHOO_IMAP_APP_PASSWORD=your-yahoo-app-password
```

See `second_brain/connectors/PREBRIEF_FOUNDATION.md` for full architecture and test coverage.

**Morning Brief handoff behavior:**
- The scheduled Morning Brief attempts a quiet prebrief run first.
- If `data/prebrief_context.json` is fresh, the brief uses only the most actionable items: due-soon bills, urgent follow-ups, worth-checking inbox updates, and notable calendar context.
- If prebrief generation fails or no fresh context exists, Morning Brief continues normally without surfacing any failure noise.

### 🌐 URL & Web Ingestion
Send a link, get it chunked and embedded. No more "I saved that article somewhere" moments.

### ✈️ Travel & Places Graph
Log places you've been, want to go, or want to remember. Searchable by city, category, country — with ratings and auto-tagging via local AI.

### 📓 Obsidian Sync
Watches your vault, incrementally ingests notes with frontmatter tags. Your curated markdown stays human-readable first, searchable second.

### 🧠 Wiki Ingestion
Create curated wiki-style notes in Obsidian from URLs. The markdown note is the source of truth; semantic indexing happens after.

### 🔭 Observability (Langfuse + OpenTelemetry-friendly)
Every slash command is automatically traced with [Langfuse](https://langfuse.com) — input, output, latency, and tags captured per run. Tracing is best-effort: commands work even if Langfuse is unreachable. Uses Langfuse Cloud (`us.cloud.langfuse.com`); add keys to `.env.local` (gitignored — never commit secrets to this public repo).

PersGraph is also **OpenTelemetry-friendly** at the architecture level: command execution, ingestion workers, and query flows are structured to support broader telemetry pipelines and monitoring as the product matures.

### 🧠 Scratchpad Workflow
Use `scratchpad/` for transient shared thinking between models. It is the working-memory layer for active topics, handoffs, and drafts. It is intentionally separate from `MEMORY.md`. Start with `scratchpad/prompts.md` and `scratchpad/template.md`.

**Stable invocation phrase:**
- `Start a scratchpad for <topic>`
- `Update the scratchpad for <topic>`
- `Handoff the scratchpad for <topic> to <model>`
- `Close the scratchpad for <topic>`

**Default routing:**
- Claude/Sonnet = advisory / critique / planning
- GPT = drafting / summarizing / options
- Haiku = execution / edits / checks

### 👨‍👩‍👧‍👦 Family Knowledge Base
Multi-user from day one. Kids ingest textbooks, PDFs, and screenshots via Telegram. Each user's content is auto-tagged — search shared knowledge or scope to your own notes. Owner routes through a powerful model; family members route cost-efficiently.

```
/ingest      → Raw URL/file ingest into semantic search
/wiki-ingest → Curated Obsidian note first, then index it
/ask         → Semantic search + answer synthesis
/note        → Quick SQLite note capture
/task        → Quick task capture
/place       → Save a place
/places      → List/search saved places
/bucketlist  → Save/list bucket list places
/digest      → On-demand summary report
/email       → Email workflow
/appointment → Save/list appointments
/schedule    → Show agenda
/debrief     → Debrief flow
/status      → System status
```

---

## Architecture

```
┌──────────────────────────────────────────┐     Private network / VPN
│  VPS host (DigitalOcean or similar)     │◄──────────────────►  Model/DB host
│  <public-host> — PRIMARY HOST           │                       <private-host>
│  · Gru (AI agent / OpenClaw)             │                       · Ollama / local models
│  · Reasoning + automation                │                       · ChromaDB vector store
│  · Telegram interface                    │                       · Embeddings & local LLMs
│  · Cron jobs & automation                │
│  · Image scanning (vision AI)            │
└──────────────────────────────────────────┘
             ▲
             │  Sensitive local files only
             │  (CC statements, portfolio PDFs)
             ▼
┌──────────────────────────┐
│  Mac (local)             │
│  · Private documents     │
└──────────────────────────┘
```

Nothing leaves your local network (except Claude API calls for agent reasoning).  
Incoming Telegram images are scanned with a vision model and auto-saved to your Obsidian vault.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Orchestration | OpenClaw (agent runtime) |
| LLM Reasoning | Anthropic Claude Sonnet |
| Local LLM + Embeddings | Ollama (Qwen2.5:7b, nomic-embed-text) |
| Vector Store | ChromaDB (self-hosted) |
| Knowledge Base | Obsidian vault |
| RAG Pipeline | Custom Python + ChromaDB |
| Finance Layer | SQLite + custom schema |
| Networking | Tailscale VPN |
| Interface | Telegram Bot + Streamlit UI |
| Tool Protocol | MCP (Model Context Protocol) |
| Ingest Formats | PDF, URL, Markdown, Email, Images, Wiki |
| Observability | Langfuse v4 + OpenTelemetry-friendly tracing architecture |

---

## What's Working

| Feature | Status |
|---|---|
| PDF ingestion → ChromaDB | ✅ Working |
| URL / web ingestion | ✅ Working |
| RAG Q&A (Qwen2.5:7b via Ollama) | ✅ Working |
| Tasks, Notes, Appointments | ✅ Working |
| `/ingest` `/wiki-ingest` `/ask` | ✅ Working |
| `/note` `/task` `/place` `/places` | ✅ Working |
| `/appointment` command | ✅ Working |
| `/schedule` command | ✅ Working |
| Appointment reminders (cron, hourly check) | ✅ Live |
| Morning Briefing (8am PST daily) | ✅ Live |
| Calendar + Email Prebrief foundation | ✅ Batch 7 complete (runner + output) |
| API cost tracking (cron, 8pm daily) | ✅ Live |
| Recurring Events manager | ✅ Working |
| Travel & POI (places graph) | ✅ Working |
| Explore Mode (Telegram POI suggestions) | ✅ Live |
| Snippets — semantic search | ✅ Working |
| Learning Agent (RAG Q&A from UI) | ✅ Working |
| Fees & Charges (SQLite-powered) | ✅ Working |
| Streamlit dashboard (9 tabs) | ✅ Live |
| Telegram image scanning → Obsidian → ChromaDB | ✅ Working |
| Multi-user (family) — per-sender tagging + model routing | ✅ Working |
| Wiki ingestion + AI synthesis | ✅ Working |
| Langfuse observability tracing | ✅ Working |
| Portfolio / financial analysis | 🔲 Phase 2 |
| Credit Card Agent (rewards + statement parsing) | 🔲 Phase 2 |
| Weekly Briefing Agent | 🔲 Phase 2 |
| YouTube ingester | 🔲 Phase 2 |

---

## Integrations

| Integration | Purpose |
|---|---|
| Gmail | Email ingestion + intent classification |
| Yahoo Mail | Read-only inbox prebrief (planned) |
| Google Calendar | Appointment sync + prebrief context |
| Telegram | Command interface + image scanning |
| Obsidian | Vault watcher + note sync |
| Ollama | Local LLM + embeddings |
| ChromaDB | Vector store |
| Google Drive | File ingestion |
| OpenClaw | AI agent runtime |
| MCP Protocol | Tool integration layer |

---

## Streamlit Dashboard (9 Tabs)

| Tab | Feature | Status |
|---|---|---|
| 🎓 Learning Agent | RAG Q&A + ingest from UI | ✅ |
| 📎 Snippets | Semantic search across knowledge base | ✅ |
| ✅ Tasks & Notes | CRUD for tasks, notes, appointments | ✅ |
| 💼 Portfolio | Financial analysis & charts | 🔲 Phase 2 |
| 💳 Credit Card Agent | Statement parsing, rewards tracking | 🔲 Phase 2 |
| 🗺️ Travel & POI | Places graph — search, ratings, map | ✅ |
| 🧠 Explore Mode | Telegram nearby suggestions + learning loop | ✅ |
| 📋 Weekly Briefing | Automated Sunday digest | 🔲 Phase 2 |
| 🔁 Recurring Events | Cron job manager + cost tracker | ✅ |
| 💸 Fees & Charges | Interest, late fees, annual fees | ✅ |

---

## Setup

```bash
git clone git@github.com:simplicoreai/Persgraph.git ~/AgenticHub/Persgraph
cd ~/AgenticHub/Persgraph
bash setup.sh
```

`setup.sh` handles everything: venv, dependencies, `.env` creation, Ollama model pull, ChromaDB check, and OpenClaw verification.

**Full step-by-step:** → [`INSTALL.md`](INSTALL.md)  
**OpenClaw agent setup:** → [`OPENCLAW_SETUP.md`](OPENCLAW_SETUP.md)

### Langfuse Observability

Every slash command is automatically traced — input, output, latency, and tags captured per run. To enable:

1. Sign up at [us.cloud.langfuse.com](https://us.cloud.langfuse.com) and create a project.
2. Add to `.env.local` (gitignored — **never** commit keys to this repo):

```env
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

3. Open your Langfuse cloud dashboard → select the **persgraph** project to browse traces.

Tracing is best-effort — all commands work even if Langfuse is unreachable. Spans are named after the slash command (e.g. `ingest`, `ask`, `note`) with the full input/output recorded.

### Services

**Option A — Docker (recommended):**
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
```bash
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

### Query your knowledge base
```bash
PYTHONPATH=. python scripts/query.py "What are my notes on RAG vs fine-tuning?"
```

### Slash commands (Telegram or terminal)

| Command | Description |
|---|---|
| `/ingest <url or file>` | Raw ingest of a URL, PDF, or web article into the search/index layer |
| `/wiki-ingest <url>` | Write a curated Obsidian wiki note first, then index it |
| `/ask <question>` | Semantic search + AI synthesis from saved content |
| `/note <text>` | Quick SQLite note capture |
| `/task <text>` | Quick task capture |
| `/place <name>` | Save a place |
| `/places [query]` | List or search saved places |
| `/email <message>` | Email workflow |
| `/appointment <title>, <date/time>` | Save or list appointments |
| `/schedule [range]` | Show your agenda |
| `/debrief` | Run the debrief flow |
| `/status` | System status |

---

## Source of Truth Model

PersGraph is simpler if each storage layer has one clear job:

- **SQLite** — operational capture
  - `/note`
  - `/task`
  - `/place`
  - `/places`
  - `/appointment`
  - `/email`
  - `/schedule`
  - `/debrief`
- **Obsidian vault** — curated markdown knowledge
  - `/wiki-ingest` writes here first
  - humans read and edit this directly
- **ChromaDB** — semantic index/search layer
  - `/ingest` writes raw source content here
  - `/ask` searches here
  - `/places` can search saved place data
  - Obsidian notes can also be indexed here
  - not the source of truth

### Command split

- **`/ingest <url or file>`**
  - raw import for retrieval/search
  - optimized for getting content into the knowledge system fast
  - primary output: indexed chunks for semantic search

- **`/wiki-ingest <url>`**
  - curated knowledge capture
  - writes a markdown note into `~/AgenticHub/InsightsData/wiki/articles/` first
  - then attempts semantic indexing
  - if indexing is down, the markdown note still exists and can be indexed later

- **`/note <text>`**
  - quick capture
  - stored in SQLite, not directly in Obsidian

  - live command surface for capture, retrieval, planning, workflow, and health checks

This keeps the mental model clean:
- where is the durable note? → Obsidian or SQLite
- where is semantic search? → ChromaDB
- what survives backend outages? → SQLite and Obsidian markdown

---

## ⚡ AI Cost & Performance Optimization

This system is built with deliberate cost-efficiency baked in — not as an afterthought.

### Tiered Model Routing

Not every task needs a frontier model. We route by complexity:

| Task Type | Model | Why |
|---|---|---|
| Heartbeats, status checks, cron | `claude-haiku-4-5` | ~20x cheaper, more than capable |
| RAG queries, slash commands | `qwen2.5:7b` (local, free) | Zero API cost — runs on your own hardware |
| Reasoning, synthesis, planning | `claude-sonnet` | Only when it actually matters |
| Embeddings | `nomic-embed-text` (local) | No API cost, no rate limits, no vendor lock-in |

**Result:** Claude API is only invoked for tasks that genuinely need it — everything else runs free on local hardware or cheaper models.

### Local-First Embeddings

All vector embeddings run on your own machine via Ollama. No OpenAI Embeddings API, no per-token billing, no data leaving your network.

```
User query → nomic-embed-text (local) → ChromaDB (local) → top-k chunks → Claude synthesis
```

This means the most-used operation in the entire system (search/retrieval) costs **$0**.

### Why Not OpenRouter?

We evaluated OpenRouter's auto-routing and decided against it for this setup:

- **Direct Anthropic is cheaper** — OpenRouter adds a ~5-10% markup; we're Anthropic-first, so it's a net negative
- **Manual routing beats auto** — We know our workload. Heartbeat = Haiku, reasoning = Sonnet. An auto-router can't be more intentional than that
- **Pinned versions = stability** — No surprise behavior changes from silent model upgrades
- **Cost tracking works cleanly** — Direct API means accurate per-model billing, no aggregation overhead

### Built-in Cost Visibility

A daily cost summary fires every evening via cron — token usage, model breakdown, cumulative spend — delivered straight to Telegram. No dashboard login required.

```bash
# Manual cost check
PYTHONPATH=. python scripts/track_api_cost.py log --tokens-in N --tokens-out N --model claude-sonnet-4-6

```

### Hybrid Architecture = Best of Both Worlds

```
Local (free, private)          Cloud (pay-per-use, powerful)
─────────────────────          ──────────────────────────────
Ollama (Qwen2.5:7b)       ←→   Claude Sonnet (complex tasks only)
ChromaDB (vector search)  ←→   Claude Haiku (cron + simple ops)
nomic-embed-text          ←→   Vision model (image scanning)
```

The goal: **maximum intelligence, minimum API spend, zero cloud lock-in on your data.**

---

## Cron Jobs

| Job | Schedule | What it does |
|---|---|---|
| `appointment-reminder` | 8:00 AM daily | Scans ChromaDB → Telegram alert if appointment within 48h |
| `morning-briefing` | 8:00 AM PST daily | Top headlines + tasks due today + appointments within 24h → Telegram |
| `api-cost-tracking` | 8:00 PM daily | Logs token usage → Telegram daily cost summary |

---

## Agentic Engineering Practices

PersGraph follows patterns from Claude Code best practices to keep AI agent context lean, scoped, and reliable.

### Scoped AGENTS.md Files

Instead of one monolithic instruction file, rules are scoped to the directory where they apply:

| File | What it governs |
|---|---|
| `AGENT_CONTEXT.md` | Root-level universal rules — collections, query behavior, security |
| `scripts/AGENTS.md` | Scripting conventions, venv path, cron IDs, error handling |
| `second_brain/AGENTS.md` | ChromaDB rules, embedding conventions, RAG behavior, tracing |
| `travel/AGENTS.md` | Trip schema, wttr.in pattern, briefing setup, UI conventions |

This mirrors the **60-line rule** from Claude Code best practices: keep the root context tight (~60 lines optimal, 200 max), and push scoped rules into subdirectory files. Beyond 200 lines, rules get quietly deprioritized by the model.

### Conditional Rule Loading

Rules that only apply in specific contexts (scripting, travel planning, ChromaDB ops) don't pollute the root context. When an agent works in `scripts/`, it loads `scripts/AGENTS.md` for precise conventions without noise from unrelated rules.

### Model Routing by Task Type

Every task routes to the cheapest capable model:
- `claude-haiku-4-5` → cron jobs, heartbeats, status checks
- Local Qwen via Ollama → RAG retrieval (free, zero API cost)
- `claude-sonnet` → reasoning, synthesis, planning only when needed

---

## Project Structure

```
persgraph/
├── README.md
├── .env.example                  # Config template
├── requirements.txt
├── docker-compose.yml
├── setup.sh                      # One-command setup
├── architecture.md               # Full system design
├── INSTALL.md                    # Step-by-step install guide
├── OPENCLAW_SETUP.md             # Agent runtime setup
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
├── scripts/
│   ├── ingest.py                 # Ingest CLI
│   ├── query.py                  # Query CLI
│   ├── command.py                # Slash command handler
│   ├── check_appointments.py     # Appointment checker (cron)
│   └── track_api_cost.py         # API cost logger (cron)
├── streamlit/
│   ├── app.py                    # Home + sidebar nav
│   └── pages/                    # 9 feature tabs
├── persgraph/                    # Standalone HTML dashboards
└── marketing/
    └── persgraph-landing.html    # Product landing page
```

---

## Privacy

PersGraph is built on a simple principle: **your personal data should never leave your machine.**

- 🔒 **100% local processing** — Ollama runs models on your CPU/GPU. No embedding API calls.
- 🏠 **Self-hosted vector DB** — ChromaDB runs on your machine or homelab.
- 🔑 **Open source** — inspect every line. No black boxes, no telemetry.
- 📡 **Air-gap ready** — works fully offline once models are pulled.
- 👤 **You own everything** — MIT licensed. Fork it, audit it, run it forever.

The only external API call is to Anthropic Claude for agent reasoning — and even then, only the query context is sent, never your raw stored data.

---

## Roadmap

**Phase 2 (in progress):**
- [ ] Portfolio & investment analysis
- [ ] Credit Card Agent — statement parsing + rewards tracking
- [ ] Weekly Briefing Agent — automated Sunday digest
- [ ] YouTube ingester
- [ ] Google Drive deep sync
- [ ] Voice ingestion via Whisper

---

## License

MIT — use it, fork it, make it yours.

---

Part of the [SimpliCore.ai](https://simplicore.ai) family of privacy-first AI tools.*
