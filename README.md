# 🧠 Second Brain

A private, local-first RAG system for your personal knowledge — PDFs, notes, emails, URLs, YouTube transcripts, and financial documents.

**Architecture:**
- 🖥️ **Mac (OpenClaw):** Orchestration, ingestion scripts, Claude for reasoning
- 🖥️ **Windows (96GB RAM):** Ollama (embeddings + LLM) + ChromaDB — all via Tailscale

Nothing leaves your local network.

---

## Setup

### 1. Install dependencies
```bash
pip install -e ".[dev]"
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your Windows Tailscale IP and model names
```

### 3. Verify connectivity
```bash
curl http://<windows-tailscale-ip>:11434/api/tags   # Ollama
curl http://<windows-tailscale-ip>:8000/api/v1/collections  # ChromaDB
```

---

## Usage

### Ingest a PDF
```bash
sb-ingest pdf ~/Documents/portfolio.pdf --tag financial --tag 2025
```

### Query your brain
```bash
sb-query "What are my portfolio returns for 2025?"
sb-query "Summarize my dental appointments" --top-k 3
```

---

## Project Structure

```
second-brain/
├── .env                      # Local config (gitignored)
├── .env.example              # Config template
├── pyproject.toml            # Package config
├── second_brain/             # Core package
│   ├── config.py             # Settings (loaded from .env)
│   ├── embeddings.py         # Ollama embedding client
│   ├── vectorstore.py        # ChromaDB wrapper
│   ├── query.py              # Query engine
│   └── ingesters/
│       ├── base.py           # Abstract base ingester
│       └── pdf.py            # PDF ingester
└── scripts/
    ├── ingest.py             # Ingest CLI
    └── query.py              # Query CLI
```

---

## Ingesters (Roadmap)

- [x] PDF
- [ ] URLs / web pages
- [ ] Notes (markdown)
- [ ] Forwarded emails
- [ ] YouTube (transcript via yt-dlp)
- [ ] Financial documents / portfolio exports
