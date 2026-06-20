# Explore Mode Cron Setup — OpenClaw Native Integration

## Overview
This document describes the proper OpenClaw-native cron integration for Explore Mode, replacing the brittle log-tail delivery pattern with structured Telegram delivery via OpenClaw's scheduler.

## Architecture

### Old Approach (Removed)
- System cron runs `scripts/explore_mode.py --check`
- Output is captured to `/tmp/explore_mode.log`
- No one monitors the log → suggestions never reach Telegram
- Brittle: depends on external log-tail script that doesn't exist

### New Approach (Implemented)
- OpenClaw cron job runs the delivery script every 60 minutes
- Script calls `check_once()` which returns `(ok, message)`
- If `ok=True` (real suggestion): prints message to stdout → Telegram delivery
- If `ok=False` (check skipped): prints nothing → no spam
- Structured, reliable, Telegram-native delivery

## Files Changed

### New Files
1. **`agents/explore-delivery/explore_deliver_suggestions.py`**
   - Runs explore mode check
   - Outputs formatted suggestion to stdout (when real suggestion exists)
   - Logs debug info to stderr
   - Designed to run from OpenClaw cron

2. **`agents/explore-delivery/__init__.py`**
   - Package marker for the delivery agent

### Modified Files
1. **System Cron (`/etc/crontab` or user crontab)**
   - Old job removed: `*/5 * * * * cd /root/AgenticHub/Persgraph && ... >> /tmp/explore_mode.log`
   - Replaced with OpenClaw cron job (see setup below)

## Setup Instructions

### For OpenClaw Gateway Admin

Run this command to create the OpenClaw cron job:

```bash
openclaw cron add \
  --name "Explore Mode Delivery" \
  --cron "0 * * * *" \
  --to "telegram:8596241969" \
  --announce \
  --timeout-seconds 30 \
  --model "litellm/fast" \
  --message "cd /root/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python agents/explore-delivery/explore_deliver_suggestions.py"
```

**Parameters:**
- `--cron "0 * * * *"` — Every 60 minutes (hourly at :00)
- `--announce` — Deliver output to Telegram as announcement
- `--to "telegram:8596241969"` — Telegram recipient (adjust ID as needed)
- `--timeout-seconds 30` — Kill job if it runs longer than 30s
- `--model "litellm/fast"` — Use fast tier (Haiku equivalent)

### Verification

After creating the cron job, verify it's working:

1. **List jobs:**
   ```bash
   openclaw cron list | grep "Explore Mode"
   ```

2. **Check status:**
   ```bash
   openclaw cron show "Explore Mode Delivery" --json
   ```

3. **Run a test:**
   ```bash
   openclaw cron run "Explore Mode Delivery"
   ```
   Expected output:
   - If Explore Mode is ON and cadence is met: formatted suggestion in Telegram
   - If Explore Mode is OFF or cadence not met: no output (silent success)

4. **Check run history:**
   ```bash
   openclaw cron runs "Explore Mode Delivery"
   ```

## Behavior

### When Explore Mode is ON and Cadence is Met
The delivery script:
1. Calls `check_once()`
2. Gets `ok=True` and formatted message
3. Prints message to stdout
4. Telegram receives announcement with the suggestion

Example output to Telegram:
```
🗺 Explore Nearby
📍 Pour Decisions Craft Coffee | Craft Beer
🆔 Event ID: `b16a6249-da2f-4096-b375-1f93eed55f8d`

🍽 Food options nearby
• Pour Decisions Craft Coffee | Craft Beer — 4.7★ • 0.7 km
...
```

### When Explore Mode is OFF or Cadence Not Met
The delivery script:
1. Calls `check_once()`
2. Gets `ok=False` and skip reason
3. Prints nothing to stdout
4. No Telegram message sent (no spam)

Examples of skip reasons:
- "explore mode is off" → User disabled Explore Mode
- "explore mode expired" → Session exceeded its duration limit
- "cadence window not reached" → Fewer than 60m (default) since last suggestion
- "location not moved significantly" → User hasn't moved far enough

## Acceptance Criteria Met

✅ **1. Explore Mode checks still run on configured cadence**
- OpenClaw cron runs every 60 minutes (configurable via `--cron`)
- System cron removed to avoid conflicts

✅ **2. Successful suggestion produces structured payload/event**
- `check_once()` returns `(ok, message)` where message is pre-formatted
- Message includes event ID for feedback tracking
- State is updated atomically in `explore_state.json`

✅ **3. Only real suggestions delivered; expired/disabled/no-op checks don't spam**
- Script prints nothing when `ok=False`
- OpenClaw only sends messages when stdout is non-empty
- Result: zero spam from expired sessions or unmet cadence windows

✅ **4. Delivery path is OpenClaw-native**
- Uses OpenClaw Gateway `cron` commands (not system cron)
- Uses OpenClaw's `--announce` delivery mode
- Uses OpenClaw's Telegram channel routing

✅ **5. TripToggle / Explore Mode state handling remains backward-compatible**
- No changes to state schema
- No changes to toggle logic
- Works with both new delivery (OpenClaw) and fallback (direct toggle response)

✅ **6. Includes verification/smoke test**
- `openclaw cron run "Explore Mode Delivery"` for on-demand test
- `openclaw cron runs "Explore Mode Delivery"` for run history
- Setup instructions documented in this file

## Testing

### Quick Smoke Test
```bash
# 1. Enable Explore Mode
cd /root/AgenticHub/Persgraph
PYTHONPATH=. .venv/bin/python agents/orchestrator/command_handler.py "/TripToggle On 2h 60m medium"

# 2. Run delivery script directly (simulates cron)
PYTHONPATH=. .venv/bin/python agents/explore-delivery/explore_deliver_suggestions.py

# 3. Check that a suggestion was printed
# (If Explore Mode is ON and first check in this cadence window)

# 4. Run again immediately (should be skipped, no output)
PYTHONPATH=. .venv/bin/python agents/explore-delivery/explore_deliver_suggestions.py
# Expected: no suggestion printed (cadence window not reached)
```

### Full Integration Test
```bash
# 1. Use OpenClaw to manually trigger the cron job
openclaw cron run "Explore Mode Delivery"

# 2. Check Telegram for the suggestion
# (Should appear if Explore Mode is ON)

# 3. Check run history
openclaw cron runs "Explore Mode Delivery"
# Should show "ok" status with delivery confirmed
```

## Fallback / Backward Compatibility

If for some reason the OpenClaw cron job is not available:
1. The old system cron setup script still exists: `scripts/setup_explore_cron.sh`
2. It can be used as a temporary fallback: `./scripts/setup_explore_cron.sh install`
3. This will install a system cron job (less preferred, but functional)
4. Once OpenClaw cron is set up, the system cron should be uninstalled

## Future Improvements

1. **Configurable schedule per user:** Allow different cadences for different users
2. **Feedback loop:** Track which suggestions lead to bookmarks/clicks
3. **Learning integration:** Suggest based on user's past preferences (Phase 2)
4. **Multi-user:** Route suggestions to multiple Telegram IDs
5. **Smart cron:** Only run when location has changed significantly (to save API quota)

## Troubleshooting

### Job not running or not delivering
1. Check OpenClaw cron status: `openclaw cron show "Explore Mode Delivery"`
2. Check job was enabled: `openclaw cron enable "Explore Mode Delivery"`
3. Check timeout hasn't been exceeded: increase `--timeout-seconds` if needed
4. Check delivery channel is correct: `--to "telegram:YOUR_ID"`

### Suggestions not appearing in Telegram
1. Verify Explore Mode is ON: `/TripToggle status`
2. Verify cadence window has passed since last suggestion
3. Verify location is available: check `data/explore_state.json` for `last_location`
4. Manually run delivery script to check for errors: `python agents/explore-delivery/explore_deliver_suggestions.py`

### Too many or too few suggestions
1. Adjust cron schedule: change `--cron "0 * * * *"` to different frequency
2. Adjust cadence in Explore Mode: `/TripToggle On 4h 30m medium` (30m cadence)
3. Check location update frequency

## See Also
- `agents/travel-scout/explore_mode.py` — Core Explore Mode logic
- `agents/orchestrator/command_handler.py` — TripToggle command implementation
- `data/explore_state.json` — Current Explore Mode session state
- `data/explore_audit.json` — Audit log of all suggestions and events
