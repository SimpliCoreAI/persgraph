# AGENT_CONTEXT.md — Second Brain Rules & Conventions

This file teaches the agent how to operate this second brain correctly.
Read this before any ingestion, query, or write operation.

> 📁 Scoped rules live in subdirectory AGENTS.md files:
> - `scripts/AGENTS.md` — scripting, cron, Telegram commands
> - `second_brain/AGENTS.md` — package, ChromaDB, embeddings, RAG
> - `travel/AGENTS.md` — trip planner, briefings, UI

---

## What This System Is

A **local-first, privacy-first second brain** running on:
- **Mac (OpenClaw):** Orchestration, ingestion scripts, Claude for reasoning
- **Windows (96GB RAM):** Ollama (qwen2.5:7b, nomic-embed-text), ChromaDB

Everything stays local. No data leaves to external services except Anthropic API calls for reasoning.

---

## Collections (ChromaDB)

| Collection   | What lives here                          | Ingested by          |
|-------------|-------------------------------------------|----------------------|
| `urls`      | Web articles, Medium posts, blog content  | `/ingest <url>`      |
| `notes`     | Personal notes, tasks, appointments       | `/note`, `/task`     |
| `pdfs`      | Financial docs, statements, manuals       | `/ingest <pdf>`      |
| `places`    | Saved restaurants, hotels, POIs           | `/place`             |
| `emails`    | Forwarded emails of interest              | queue worker         |
| `youtube`   | YouTube video transcripts                 | `/ingest <yt-url>`   |

**Rules:**
- NEVER mix content types across collections
- Always tag with at minimum: source_type + topic tags
- Each chunk must carry: `source`, `title`, `domain`, `ingested_at`, `tags`, `source_type`

---

## Tagging Conventions

Tags are comma-separated strings in chunk metadata. Always include:
- **source_type:** `medium`, `youtube`, `pdf`, `note`, `place`, `email`, `web`
- **topic tags:** descriptive, kebab-case (e.g., `second-brain`, `llm`, `finance`, `travel`)
- **date context** (optional): `2026`, `q2-2026`

Examples:
- Medium article: `medium, llm, obsidian, second-brain`
- Bank statement: `pdf, finance, credit-card, 2026`
- Saved note: `note, idea, project-x`

---

## Slash Commands

These are the primary ways to interact with the second brain via Telegram:

| Command | What it does |
|---------|-------------|
| `/ingest <url>` | Ingest a web URL or YouTube link into the brain |
| `/ask <question>` | Query the brain and get a synthesized answer |
| `/note <text>` | Save a quick note or thought |
| `/task <text>` | Save a task or to-do |
| `/place <name>, <city>` | Save a place/restaurant/POI |
| `/remind <text> at <time>` | Set a reminder |
| `/status` | Show queue stats, collection counts |

---

## Query Behavior Rules

When answering `/ask` queries:
1. **Always cite sources** — include the source URL or title in your answer
2. **Signal inference** — if the answer requires reasoning beyond stored facts, say "Inferring from [source]..."
3. **Admit gaps** — if the brain doesn't have enough info, say so clearly. Don't hallucinate.
4. **Suggest next steps** — if relevant info is missing, suggest: "Want me to ingest X to fill this in?"

---

## Ingestion Rules

Before ingesting any URL:
- Duplicate detection is automatic via chunk IDs
- For Medium/paywalled articles: use `https://freedium-mirror.cfd/<url>` (try original first)
- For YouTube: extract transcript, not just metadata

After ingestion: report chunks_total, chunks_new, collection, tags.

> Full scripting conventions → `scripts/AGENTS.md`

---

## Security & Privacy

- All data is local — no external storage
- PDFs with financial data: stored in `pdfs` collection, never logged to console
- Vault is git-tracked for rollback: `cd ~/AgenticHub/Persgraph && git log --oneline`
- If an agent action seems destructive, STOP and confirm with user first

---

## Evolution Notes

Things to build next (tracked here, not in code):
- [ ] YouTube transcript ingester
- [ ] PDF Portfolio tab (Streamlit)
- [ ] Weekly Briefing Agent (Sunday 8AM)
- [ ] CC Statement parser
- [ ] Richer frontmatter on all chunks (type, source_type)
