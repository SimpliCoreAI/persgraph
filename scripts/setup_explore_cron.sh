#!/bin/bash
#
# Explore Mode — Cron Setup & Installation
# Safe, idempotent cron job configuration for Explore Mode
#
# Usage:
#   ./setup_explore_cron.sh install    # Add cron job
#   ./setup_explore_cron.sh uninstall  # Remove cron job
#   ./setup_explore_cron.sh status     # Show current config
#

set -e

# Get script directory (where this file lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CRON_SCRIPT="$SCRIPT_DIR/explore_mode.py"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
JOB_NAME="PersGraph Explore Mode"
JOB_COMMENT="PersGraph-Explore-Mode-Cron"
SCHEDULE="0 * * * *"  # Every hour (requested by Jolly)

# Verify dependencies
check_deps() {
    if [[ ! -f "$CRON_SCRIPT" ]]; then
        echo "❌ Error: explore_mode.py not found at $CRON_SCRIPT"
        exit 1
    fi
    
    if [[ ! -f "$VENV_PYTHON" ]]; then
        echo "❌ Error: Python venv not found at $VENV_PYTHON"
        exit 1
    fi
}

# Generate cron line
get_cron_line() {
    cat <<EOF
$SCHEDULE cd $REPO_ROOT && PYTHONPATH=. $VENV_PYTHON scripts/explore_mode.py --check >> /tmp/explore_mode.log 2>&1 # $JOB_COMMENT
EOF
}

# Install cron job (idempotent)
install_cron() {
    check_deps
    
    echo "📋 Installing Explore Mode cron job..."
    
    # Get current crontab (or empty if none)
    CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")
    
    NEW_LINE="$(get_cron_line)"

    # Replace existing job if present, otherwise append it.
    if echo "$CURRENT_CRON" | grep -q "$JOB_COMMENT"; then
        NEW_CRON=$(echo "$CURRENT_CRON" | grep -v "$JOB_COMMENT")
        NEW_CRON=$(cat <<EOF
$NEW_CRON
$NEW_LINE
EOF
        )
    else
        NEW_CRON=$(cat <<EOF
$CURRENT_CRON
$NEW_LINE
EOF
        )
    fi

    # Remove leading/trailing blank lines
    NEW_CRON=$(echo "$NEW_CRON" | sed '/^[[:space:]]*$/d')

    # Install
    echo "$NEW_CRON" | crontab -

    echo "✅ Explore Mode cron job installed/updated:"
    echo "$NEW_LINE"
    echo ""
    echo "📝 Logs: /tmp/explore_mode.log"
    echo "💡 Check enable status: cd $REPO_ROOT && $VENV_PYTHON scripts/explore_mode.py --status"
    echo "💡 Current mode expires based on /TripToggle duration, not cron itself."
    echo "💡 Cron cadence is hourly unless updated here."
}

# Uninstall cron job
uninstall_cron() {
    echo "🗑️  Uninstalling Explore Mode cron job..."
    
    CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")
    
    if ! echo "$CURRENT_CRON" | grep -q "$JOB_COMMENT"; then
        echo "⚠️  Cron job not found. Nothing to remove."
        return 0
    fi
    
    # Remove the job
    NEW_CRON=$(echo "$CURRENT_CRON" | grep -v "$JOB_COMMENT")
    
    if [[ -z "$NEW_CRON" ]]; then
        # No jobs left, remove crontab entirely
        crontab -r 2>/dev/null || true
        echo "✅ Cron job removed (all jobs deleted)."
    else
        echo "$NEW_CRON" | crontab -
        echo "✅ Explore Mode cron job removed."
    fi
}

# Show status
show_status() {
    check_deps
    
    echo "🔍 Explore Mode Cron Status"
    echo "---"
    echo "Repository: $REPO_ROOT"
    echo ""
    
    CURRENT_CRON=$(crontab -l 2>/dev/null || echo "(no crontab)")
    
    if echo "$CURRENT_CRON" | grep -q "$JOB_COMMENT"; then
        echo "✅ Cron job: INSTALLED"
        echo ""
        echo "Scheduled job:"
        echo "$CURRENT_CRON" | grep "$JOB_COMMENT"
    else
        echo "❌ Cron job: NOT INSTALLED"
        echo ""
        echo "To install, run: $0 install"
    fi
    
    echo ""
    echo "Explore Mode state:"
    cd "$REPO_ROOT" && $VENV_PYTHON scripts/explore_mode.py --status 2>/dev/null || echo "(error reading state)"
}

# Main
main() {
    case "${1:-status}" in
        install)
            install_cron
            ;;
        uninstall)
            uninstall_cron
            ;;
        status)
            show_status
            ;;
        *)
            echo "Usage: $0 {install|uninstall|status}"
            echo ""
            echo "Commands:"
            echo "  install    — Add cron job to schedule Explore Mode checks every 60 minutes"
            echo "  uninstall  — Remove Explore Mode cron job"
            echo "  status     — Show current cron installation status"
            echo ""
            echo "Repository: $REPO_ROOT"
            exit 1
            ;;
    esac
}

main "$@"
