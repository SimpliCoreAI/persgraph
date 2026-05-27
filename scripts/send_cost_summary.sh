#!/bin/bash
# Daily API Cost Summary — runs at 8pm via cron
# Generates summary and sends to Telegram via OpenClaw

cd /Users/jasleenkaur/AgenticHub/Persgraph

# Generate summary JSON
SUMMARY=$(PYTHONPATH=. python3 scripts/track_api_cost.py summary 2>/dev/null)

if [ -z "$SUMMARY" ]; then
  echo "ERROR: Could not generate summary" >&2
  exit 1
fi

# Parse values with python
MSG=$(python3 -c "
import json, sys
data = json.loads('''$SUMMARY''')
daily = data.get('daily', {})
total = data.get('total', {})

dates = sorted(daily.keys(), reverse=True)
today = dates[0] if dates else 'N/A'
yesterday = dates[1] if len(dates) > 1 else 'N/A'

def fmt(d):
    r = daily.get(d, {})
    cost = r.get('cost_usd', 0)
    ti = r.get('input_tokens', 0)
    to_ = r.get('output_tokens', 0)
    calls = r.get('calls', 0)
    return f'\${cost:.2f} ({ti//1000}k in / {to_//1000}k out, {calls} calls)'

seven_day = sum(v.get('cost_usd', 0) for v in daily.values())
total_cost = total.get('cost_usd', 0)

lines = [
    '📊 API Cost Summary',
    f'Today ({today}): {fmt(today)}',
    f'Yesterday ({yesterday}): {fmt(yesterday)}',
    f'7-day total: \${seven_day:.2f}',
    f'All-time total: \${total_cost:.2f}',
]
print('\n'.join(lines))
" 2>/dev/null)

if [ -z "$MSG" ]; then
  MSG="📊 API Cost Summary\nError parsing data — check /tmp/api_cost_debug.json"
  echo "$SUMMARY" > /tmp/api_cost_debug.json
fi

# Send via OpenClaw to Telegram
/usr/local/bin/openclaw message send \
  --channel telegram \
  --target "8596241969" \
  --message "$MSG" 2>/dev/null

# Update last_cost_summary_date in heartbeat state
TODAY=$(date +%Y-%m-%d)
python3 -c "
import json
from pathlib import Path
state_file = Path('/Users/jasleenkaur/AgenticHub/Persgraph/data/heartbeat-state.json')
state = json.loads(state_file.read_text()) if state_file.exists() else {}
state['last_cost_summary_date'] = '$TODAY'
state_file.write_text(json.dumps(state, indent=2))
print('State updated')
" 2>/dev/null

echo "Cost summary sent for $TODAY"
