# second_brain/AGENTS.md — Core Package Conventions

## Package Rules
- `second_brain.*` is the core package — import from here, not from scripts
- All config via `second_brain.config` (pydantic-settings, reads config.yaml + .env)
- ChromaDB client lives in `vectorstore.py` — never instantiate directly elsewhere
- Embeddings client lives in `embeddings.py` — local/remote Ollama via config or env

## ChromaDB Conventions
- Collections: `urls`, `notes`, `pdfs`, `places`, `emails`, `youtube` — NEVER mix
- Chunk metadata required: `source`, `title`, `domain`, `ingested_at`, `tags`, `source_type`
- Chunk size: 512 tokens, overlap: 64 tokens
- Duplicate detection: automatic via chunk IDs — don't re-ingest manually

## Embeddings
- Model: `nomic-embed-text` on Ollama (host configured via env/config)
- If the model host is offline: embeddings will fail — check connectivity before bulk ingestion
- Never call OpenAI/Anthropic for embeddings — local only

## Query / RAG Engine
- All retrieval goes through `second_brain.query`
- Always cite source in returned answers
- Signal inference vs. retrieved facts explicitly
- If <3 relevant chunks found: say so, suggest ingesting more

## Tracing
- Langfuse tracing in `tracing.py` — wrap LLM calls with trace context
- Do not add print-debugging inside traced functions — breaks span timing

## Adding New Features
- New ingesters: add to `second_brain/ingesters/`, register in command.py
- New slash commands: add handler in `scripts/command.py`, document in root AGENT_CONTEXT.md
- Schema changes to SQLite notes/places: write a migration script in `scripts/`
