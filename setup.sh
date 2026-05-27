#!/usr/bin/env bash
# =============================================================================
# 🧠 PersGraph — Full Setup Script
# Sets up the second brain: venv, deps, .env, Ollama models, ChromaDB check
# Run: bash setup.sh
# =============================================================================

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; exit 1; }
step() { echo -e "\n${YELLOW}── $* ──${NC}"; }

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║        🧠  PersGraph Second Brain Setup           ║"
echo "║   Personal knowledge base — local & private      ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ── 1. Python ─────────────────────────────────────────────────────────────────
step "1. Python version check"
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3.9 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
    MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$cmd"
      ok "Found $("$cmd" --version)"
      break
    fi
  fi
done
[ -z "$PYTHON" ] && err "Python 3.9+ required. Install from https://python.org/downloads"

# ── 2. Virtual environment ────────────────────────────────────────────────────
step "2. Virtual environment"
if [ -d ".venv" ]; then
  ok "Found existing .venv"
else
  echo "   Creating .venv..."
  "$PYTHON" -m venv .venv
  ok "Virtual environment created"
fi

# Activate
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
else
  warn "Could not activate venv — continuing with system Python"
fi

# ── 3. Dependencies ───────────────────────────────────────────────────────────
step "3. Installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Dependencies installed"

# Streamlit extras (optional)
if [ -f "streamlit/requirements.txt" ]; then
  pip install -q -r streamlit/requirements.txt
  ok "Streamlit extras installed"
fi

# ── 4. Environment config ─────────────────────────────────────────────────────
step "4. Environment configuration"
if [ -f ".env" ]; then
  ok ".env already exists — skipping"
else
  cp .env.example .env
  ok "Copied .env.example → .env"
  echo ""
  echo "   📝 Open .env and fill in your values:"
  echo "      WINDOWS_IP, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GOG_ACCOUNT"
  echo "      (or leave WINDOWS_IP blank if using Docker / local Ollama)"
fi

# ── 5. Ollama check ───────────────────────────────────────────────────────────
step "5. Ollama (local LLM + embeddings)"

# Load .env for OLLAMA_BASE_URL if set
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "   Checking Ollama at $OLLAMA_URL..."
if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
  ok "Ollama is running"

  # Pull required models if not present
  TAGS=$(curl -sf "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
names = [m['name'] for m in data.get('models', [])]
print(' '.join(names))
" 2>/dev/null || echo "")

  for model in "nomic-embed-text" "qwen2.5:7b"; do
    if echo "$TAGS" | grep -q "${model%%:*}"; then
      ok "Model ready: $model"
    else
      echo "   ⬇️  Pulling $model (this may take a few minutes)..."
      curl -sf -X POST "$OLLAMA_URL/api/pull" -d "{\"name\":\"$model\"}" > /dev/null && ok "Pulled $model" || warn "Could not pull $model — pull manually: ollama pull $model"
    fi
  done
else
  warn "Ollama not reachable at $OLLAMA_URL"
  echo ""
  echo "   Options:"
  echo "   A) Run Ollama locally:  https://ollama.com → install → ollama serve"
  echo "   B) Use Docker:          docker compose up -d  (includes Ollama + ChromaDB)"
  echo "   C) Remote machine:      set OLLAMA_BASE_URL in .env"
fi

# ── 6. ChromaDB check ────────────────────────────────────────────────────────
step "6. ChromaDB (vector store)"
CHROMA_HOST="${CHROMA_HOST:-localhost}"
CHROMA_PORT="${CHROMA_PORT:-8000}"

if curl -sf "http://$CHROMA_HOST:$CHROMA_PORT/api/v1/heartbeat" > /dev/null 2>&1; then
  ok "ChromaDB is running at $CHROMA_HOST:$CHROMA_PORT"
else
  # Check if local chroma_db folder exists (embedded mode)
  if [ -f "chroma_db/chroma.sqlite3" ]; then
    ok "Using embedded ChromaDB (chroma_db/)"
  else
    warn "ChromaDB not reachable at $CHROMA_HOST:$CHROMA_PORT"
    echo ""
    echo "   Options:"
    echo "   A) Use Docker:   docker compose up -d  (starts ChromaDB automatically)"
    echo "   B) Run locally:  pip install chromadb && chroma run --path ./chroma_db"
    echo "   C) Embedded:     already works out-of-the-box for most commands"
  fi
fi

# ── 7. OpenClaw check ─────────────────────────────────────────────────────────
step "7. OpenClaw (AI agent layer)"
if command -v openclaw &>/dev/null; then
  ok "OpenClaw installed: $(openclaw --version 2>/dev/null || echo 'found')"
else
  warn "OpenClaw not found"
  echo ""
  echo "   Install: npm install -g openclaw"
  echo "   Then run: openclaw setup"
  echo "   Docs: https://docs.openclaw.ai"
fi

# ── 8. gog (Google Workspace CLI) ────────────────────────────────────────────
step "8. gog — Google Workspace CLI (optional)"
if command -v gog &>/dev/null; then
  ok "gog installed"
  echo "   If not authed yet: gog auth login --account your@gmail.com"
else
  warn "gog not found (needed for Gmail / Calendar / Drive)"
  echo "   Install: npm install -g @openclaw/gog"
  echo "   Auth:    gog auth login --account your@gmail.com"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  🎉 Setup complete!                               ║"
echo "║                                                   ║"
echo "║  Next steps:                                      ║"
echo "║  1. Edit .env with your values                   ║"
echo "║  2. openclaw start                               ║"
echo "║  3. Ingest something:                            ║"
echo "║     PYTHONPATH=. .venv/bin/python \\              ║"
echo "║       scripts/command.py \"/ingest <url>\"          ║"
echo "║                                                   ║"
echo "║  Full guide: INSTALL.md                          ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
