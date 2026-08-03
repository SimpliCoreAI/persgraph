#!/usr/bin/env bash
# =============================================================================
# 🎉 PersGraph Setup — one-click install & launch
# =============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          🎉  PersGraph Setup                     ║"
echo "║  Personal finance analytics — local & private   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python 3.9+ ─────────────────────────────────────────────────────
echo "🔍 Checking Python version..."

PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "(0, 0)")
    MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
    MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$cmd"
      echo "   ✅ Found $("$cmd" --version)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "   ❌ Python 3.9+ is required but not found."
  echo "      Install it from https://www.python.org/downloads/ and re-run setup.sh"
  exit 1
fi

# ── 2. Virtualenv ─────────────────────────────────────────────────────────────
echo ""
echo "📦 Setting up virtual environment..."

VENV_PATH=""

# Prefer parent second-brain .venv if it exists and has pip
PARENT_VENV="../.venv"
if [ -f "$PARENT_VENV/bin/pip" ] || [ -f "$PARENT_VENV/Scripts/pip.exe" ]; then
  echo "   ♻️  Using parent second-brain .venv at $PARENT_VENV"
  VENV_PATH="$PARENT_VENV"
elif [ -d ".venv" ]; then
  echo "   ♻️  Using existing persgraph .venv"
  VENV_PATH=".venv"
else
  echo "   🔨 Creating new .venv in persgraph/..."
  "$PYTHON" -m venv .venv
  VENV_PATH=".venv"
  echo "   ✅ Virtual environment created"
fi

# Activate venv
if [ -f "$VENV_PATH/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV_PATH/bin/activate"
elif [ -f "$VENV_PATH/Scripts/activate" ]; then
  # Windows Git Bash
  # shellcheck disable=SC1091
  source "$VENV_PATH/Scripts/activate"
else
  echo "   ⚠️  Could not activate venv — continuing with system Python"
fi

PIP="$(command -v pip3 || command -v pip)"

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo ""
echo "📥 Installing dependencies (pandas, plotly)..."
"$PIP" install pandas plotly -q
echo "   ✅ Dependencies installed"

# ── 4. .env.local check ───────────────────────────────────────────────────────
echo ""
if [ -f "../.env.local" ]; then
  echo "✅ Found ../.env.local — skipping host configuration"
else
  echo "🌐 Network configuration"
  echo "   (needed for Windows-hosted Ollama/ChromaDB over VPN)"
  printf "   Enter Ollama/ChromaDB host IP (press Enter to skip if local): "
  read -r HOST_IP
  if [ -n "$HOST_IP" ]; then
    cat > "../.env.local" <<EOF
OLLAMA_BASE_URL=http://${HOST_IP}:11434
CHROMA_HOST=${HOST_IP}
EOF
    echo "   ✅ Written ../.env.local with host IP: $HOST_IP"
  else
    echo "   ⏭  Skipped — using localhost defaults"
  fi
fi

# ── 5. Check for CSV data ─────────────────────────────────────────────────────
echo ""
echo "📂 Checking data/ folder..."
mkdir -p data

CSV_COUNT=$(find data/ -maxdepth 1 -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')

if [ "$CSV_COUNT" -eq 0 ]; then
  echo ""
  echo "⚠️  No CSV files found in persgraph/data/"
  echo ""
  echo "   Drop your transaction CSVs here:"
  echo "   ~/AgenticHub/Persgraph/persgraph/data/"
  echo ""
  echo "   Expected filenames:"
  echo "     transactions_2025.csv   — full year 2025"
  echo "     transactions_2026.csv   — 2026 YTD"
  echo ""
  echo "   Expected columns: Date, Account, Description, Category, Tags, Amount"
  echo ""
  echo "   Re-run ./setup.sh after dropping in your CSVs."
else
  echo "   ✅ Found $CSV_COUNT CSV file(s) — running analysis..."
  echo ""

  # ── 6. Run analysis scripts ──────────────────────────────────────────────────
  run_script() {
    local script="$1"
    local label="$2"
    if [ -f "$script" ]; then
      echo "   ▶  $label..."
      "$PYTHON" "$script" && echo "      ✅ $label complete" || echo "      ⚠️  $label failed (check output above)"
    else
      echo "   ⏭  $script not found — skipping"
    fi
  }

  run_script "analyze_2025.py"          "2025 analysis"
  run_script "analyze_transactions.py"  "2026 YTD analysis"
  run_script "analyze_yoy.py"           "Year-over-year analysis"
  run_script "analyze_portfolio.py"     "Portfolio 2025+2026 analysis"
fi

# ── 7. Start serve.py ─────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting local server on port 8765..."

# Kill anything already on 8765
if command -v lsof &>/dev/null; then
  OLD_PID=$(lsof -ti :8765 2>/dev/null || true)
  if [ -n "$OLD_PID" ]; then
    echo "   🔪 Killing existing process on port 8765 (PID $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
elif command -v fuser &>/dev/null; then
  fuser -k 8765/tcp 2>/dev/null || true
  sleep 1
fi

if [ -f "serve.py" ]; then
  nohup "$PYTHON" serve.py > /tmp/persgraph-serve.log 2>&1 &
  SERVER_PID=$!
  echo "   ✅ Server started (PID $SERVER_PID) — logs: /tmp/persgraph-serve.log"
  sleep 1
else
  echo "   ⚠️  serve.py not found — skipping server start"
  echo "      Run '$PYTHON serve.py' (or ./setup.sh) manually when ready"
fi

# ── 8. Open browser ───────────────────────────────────────────────────────────
DASHBOARD_URL="http://localhost:8765/dashboard.html"

if [ -f "dashboard.html" ]; then
  echo ""
  echo "🌐 Opening dashboard in browser..."
  if command -v open &>/dev/null; then
    open "$DASHBOARD_URL"         # macOS
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$DASHBOARD_URL"     # Linux
  elif command -v start &>/dev/null; then
    start "$DASHBOARD_URL"        # Windows Git Bash
  else
    echo "   (Could not auto-open browser — open manually)"
  fi
else
  echo "   ⚠️  dashboard.html not found — skipping browser open"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ PersGraph is running at                      ║"
echo "║     http://localhost:8765                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
