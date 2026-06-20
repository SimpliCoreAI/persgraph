#!/bin/bash
#
# Explore Mode Delivery — Validation & Testing Script
#
# This script validates the new OpenClaw-native Explore Mode delivery setup.
# It tests both the delivery script and the integration with the cron system.
#
# Usage:
#   ./scripts/validate_explore_delivery.sh          # Run all checks
#   ./scripts/validate_explore_delivery.sh syntax   # Just syntax check
#   ./scripts/validate_explore_delivery.sh import   # Just import check
#   ./scripts/validate_explore_delivery.sh delivery # Just delivery behavior
#   ./scripts/validate_explore_delivery.sh cron     # Just check cron status
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
DELIVERY_SCRIPT="$REPO_ROOT/agents/explore-delivery/explore_deliver_suggestions.py"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_fail() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

echo_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Test: Syntax check
test_syntax() {
    echo ""
    echo_info "Testing: Python syntax"
    if $VENV_PYTHON -m py_compile "$DELIVERY_SCRIPT" 2>&1; then
        echo_pass "Syntax check passed"
    else
        echo_fail "Syntax check failed"
    fi
}

# Test: Import check
test_imports() {
    echo ""
    echo_info "Testing: Module imports"
    $VENV_PYTHON - <<'PYEOF'
import importlib.util
from pathlib import Path
import sys

ROOT = Path('/root/AgenticHub/Persgraph')
sys.path.insert(0, str(ROOT))

# Test dynamic loading
module_path = ROOT / 'agents' / 'travel-scout' / 'explore_mode.py'
spec = importlib.util.spec_from_file_location('travel_scout.explore_mode', module_path)
explore_mode_module = importlib.util.module_from_spec(spec)
sys.modules['travel_scout.explore_mode'] = explore_mode_module
spec.loader.exec_module(explore_mode_module)

from travel_scout.explore_mode import check_once, load_state
print("Dynamic imports successful")
PYEOF
    if [ $? -eq 0 ]; then
        echo_pass "Import check passed"
    else
        echo_fail "Import check failed"
    fi
}

# Test: Delivery script behavior
test_delivery() {
    echo ""
    echo_info "Testing: Delivery script behavior"
    
    # Create temporary state file for testing
    test_state_file="$REPO_ROOT/data/explore_state.json.test"
    
    echo "Running delivery script (should handle expired state gracefully)..."
    cd "$REPO_ROOT" && PYTHONPATH=. $VENV_PYTHON "$DELIVERY_SCRIPT" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo_pass "Delivery script executed successfully"
    else
        echo_fail "Delivery script failed"
    fi
}

# Test: Cron status
test_cron_status() {
    echo ""
    echo_info "Testing: OpenClaw cron status"
    
    if command -v openclaw &> /dev/null; then
        echo "OpenClaw CLI found. Checking cron jobs..."
        
        if openclaw cron list 2>&1 | grep -q "Explore Mode"; then
            echo_pass "Explore Mode cron job is registered in OpenClaw"
        else
            echo_warn "Explore Mode cron job not found in OpenClaw (may need to be created)"
            echo ""
            echo "To create the job, run:"
            echo "  openclaw cron add \\"
            echo "    --name 'Explore Mode Delivery' \\"
            echo "    --cron '0 * * * *' \\"
            echo "    --to 'telegram:8596241969' \\"
            echo "    --announce \\"
            echo "    --timeout-seconds 30 \\"
            echo "    --model 'litellm/fast' \\"
            echo "    --message 'cd /root/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python agents/explore-delivery/explore_deliver_suggestions.py'"
        fi
    else
        echo_warn "OpenClaw CLI not found (install OpenClaw to manage cron jobs)"
    fi
}

# Test: File structure
test_files() {
    echo ""
    echo_info "Testing: File structure"
    
    files=(
        "$DELIVERY_SCRIPT"
        "$REPO_ROOT/agents/explore-delivery/__init__.py"
        "$REPO_ROOT/agents/travel-scout/explore_mode.py"
        "$REPO_ROOT/data/explore_state.json"
    )
    
    all_exist=true
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            echo_pass "Found: $file"
        else
            echo_fail "Missing: $file"
            all_exist=false
        fi
    done
    
    if [ "$all_exist" = true ]; then
        echo_pass "All required files present"
    fi
}

# Test: Old cron removal
test_old_cron() {
    echo ""
    echo_info "Testing: Old system cron removal"
    
    if crontab -l 2>/dev/null | grep -q "Explore-Mode"; then
        echo_warn "Old system cron job still exists (should be removed)"
        echo ""
        echo "To remove it:"
        echo "  crontab -e"
        echo "  Delete the line containing 'PersGraph-Explore-Mode-Cron'"
    else
        echo_pass "Old system cron job properly removed"
    fi
}

# Main menu
run_all() {
    echo "========================================"
    echo "Explore Mode Delivery — Validation Suite"
    echo "========================================"
    
    test_files
    test_syntax
    test_imports
    test_delivery
    test_old_cron
    test_cron_status
    
    echo ""
    echo "========================================"
    echo_pass "Validation complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "1. Enable Explore Mode: /TripToggle On 2h 60m medium"
    echo "2. Create OpenClaw cron job (see instructions above)"
    echo "3. Run: openclaw cron run 'Explore Mode Delivery'"
    echo "4. Check Telegram for the suggestion"
    echo ""
}

# Parse command-line arguments
case "${1:-all}" in
    all)
        run_all
        ;;
    syntax)
        test_syntax
        ;;
    import)
        test_imports
        ;;
    delivery)
        test_delivery
        ;;
    cron)
        test_cron_status
        ;;
    *)
        echo "Usage: $0 {all|syntax|import|delivery|cron}"
        echo ""
        echo "Options:"
        echo "  all       — Run all validation checks (default)"
        echo "  syntax    — Python syntax check only"
        echo "  import    — Module import check only"
        echo "  delivery  — Test delivery script behavior"
        echo "  cron      — Check OpenClaw cron status"
        exit 1
        ;;
esac
