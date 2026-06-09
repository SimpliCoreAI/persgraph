# 🧠 PersGraph — Install Guide

Get up and running in ~10 minutes.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.9+ | [python.org](https://python.org/downloads) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| OpenClaw | latest | `npm install -g openclaw` |
| Docker *(optional)* | any | [docker.com](https://docker.com) — only needed if not running Ollama natively |

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/SimpliCoreAI/persgraph.git ~/AgenticHub/Persgraph
cd ~/AgenticHub/Persgraph
```

---

## Step 2 — Run setup

```bash
bash setup.sh
```

This will:
- Create a Python venv and install all dependencies
- Copy `.env.example` → `.env`
- Check/pull Ollama models (`nomic-embed-text`, `qwen2.5:7b`)
- Verify ChromaDB is reachable
- Check for OpenClaw and gog

---

## Step 3 — Configure `.env`

Open `.env` and fill in your values:

```bash
nano .env   # or open in any editor
```

Key fields:

```env
# ── Ollama ─────────────────────────────────────────────
# If running locally (native or Docker):
OLLAMA_BASE_URL=http://localhost:11434

# If running on a remote machine (e.g. Windows over Tailscale):
# OLLAMA_BASE_URL=http://100.x.x.x:11434

# ── ChromaDB ───────────────────────────────────────────
CHROMA_HOST=localhost
CHROMA_PORT=8000

# ── Telegram (for alerts from OpenClaw) ────────────────
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# ── Google (for Gmail / Calendar / Drive via gog) ──────
GOG_ACCOUNT=you@gmail.com
```

> **Telegram setup:** Create a bot via [@BotFather](https://t.me/botfather), grab the token, then get your chat ID from [@userinfobot](https://t.me/userinfobot).

---

## Step 4 — Start services

### Option A: Docker (recommended for new setups)

Starts Ollama + ChromaDB locally. No separate installs needed.

```bash
docker compose up -d
```

Wait ~30s for Ollama to pull models on first run, then verify:

```bash
curl http://localhost:11434/api/tags     # Ollama OK
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB OK
```

### Option B: Native Ollama

```bash
# Install from https://ollama.com
ollama serve &                     # start server
ollama pull nomic-embed-text       # embedding model
ollama pull qwen2.5:7b             # fast LLM
```

ChromaDB embedded mode works out-of-the-box — no separate server needed for basic use.

---

## Step 5 — OpenClaw setup

```bash
openclaw setup        # interactive wizard
openclaw start        # start the agent gateway
```

Configure your workspace:

```bash
# Point OpenClaw at this repo
openclaw config set workspace ~/AgenticHub/Persgraph
```

---

## Step 6 — Google auth (optional, for Gmail/Calendar/Drive)

```bash
npm install -g @openclaw/gog
gog auth login --account your@gmail.com
```

You'll be redirected to Google OAuth. Enable these APIs in your [Google Cloud Console](https://console.cloud.google.com):
- Gmail API
- Google Calendar API
- Google Drive API
- Google Contacts API

---

## Step 7 — Test it

```bash
# Activate venv first
source .venv/bin/activate

# Ask a question (will say "no docs yet" on fresh install — that's fine)
PYTHONPATH=. python scripts/command.py "/ask what do I know about coffee shops"

# Ingest a URL
PYTHONPATH=. python scripts/command.py "/ingest https://en.wikipedia.org/wiki/Specialty_coffee"

# Add a place
PYTHONPATH=. python scripts/command.py "/place Blue Bottle Coffee, SF, best single origin espresso"

# Check status
PYTHONPATH=. python scripts/command.py "/status"
```

---

## Common slash commands

| Command | What it does |
|---------|-------------|
| `/ingest <url or file>` | Raw-ingest a URL, PDF, or text into the semantic index |
| `/ask <question>` | Semantic search + AI synthesis from your saved data |
| `/note <text>` | Save a quick note to SQLite |
| `/place <name, location, notes>` | Save a point of interest |
| `/task <description>` | Add a task |
| `/wiki-ingest <url>` | Write a curated Obsidian wiki note from a URL, then index it |
| `/status` | Check system status |

---

## Troubleshooting

**Ollama not reachable**
```bash
# Check it's running
curl http://localhost:11434/api/tags
# If not: ollama serve  (or docker compose up -d)
```

**ChromaDB connection error**
```bash
# For Docker:
docker compose ps
docker compose logs chromadb
# For embedded: chroma_db/ folder is created automatically on first use
```

**`ModuleNotFoundError`**
```bash
# Make sure venv is activated
source .venv/bin/activate
pip install -r requirements.txt
```

**OpenClaw not starting**
```bash
openclaw status       # check what's wrong
openclaw restart      # restart gateway
```

**gog auth issues**
- Make sure the Google APIs are enabled in your Cloud Console
- Re-run: `gog auth login --account your@gmail.com`

---

## Architecture overview

```
You → Telegram → OpenClaw (main agent)
                     │
                     ├── /ask, /ingest, /note, /place
                     │         │
                     │   second_brain/ (Python)
                     │         │
                     │    ┌────┴────────────────┐
                     │    │  ChromaDB           │  ← vector search
                     │    │  Ollama (embed+LLM) │  ← local AI
                     │    │  Obsidian vault     │  ← note storage
                     │    └─────────────────────┘
                     │
                     └── Gmail / Calendar / Drive (via gog)
```

---

## File layout

```
Persgraph/
├── setup.sh              ← this setup script
├── docker-compose.yml    ← Ollama + ChromaDB via Docker
├── INSTALL.md            ← you are here
├── .env.example          ← copy to .env and fill in
├── config.yaml           ← paths and model settings
├── requirements.txt      ← Python dependencies
├── second_brain/         ← core library (ingest, query, places, notes)
├── scripts/              ← CLI entry points (command.py, ingest.py, etc.)
├── streamlit/            ← optional Streamlit dashboard
└── persgraph/            ← finance analytics (separate feature)
```

---

*Questions? Check the README or ping the agent.*
