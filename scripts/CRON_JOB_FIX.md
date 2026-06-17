# Persgraph Queue Worker Cron Job Fix

## Problem
The OpenClaw cron job `fb47be38-2b39-4372-8e29-052d86dc19cd` (Persgraph Queue Worker) was calling:
```bash
PYTHONPATH=. .venv/bin/python -c "from second_brain.queue import process_queue; process_queue()"
```

This fails with `ImportError: cannot import name 'process_queue' from 'second_brain.queue'` because the queue module does not export a `process_queue` function.

## Root Cause
- `second_brain/queue.py` provides utility functions: `enqueue()`, `pending()`, `mark_done()`, etc.
- The actual worker logic is in `scripts/queue_worker.py`
- The worker's main function is `run()` which processes pending queue items

## Fix
Replace the cron job message with:
```bash
cd ~/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python scripts/queue_worker.py
```

## Verification
Direct execution test:
```
$ cd /root/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python scripts/queue_worker.py
QUEUE_PROCESSED: ok
```

✅ Script runs cleanly and reports status.

## File Changes
- **Modified**: `scripts/queue_worker.py` — no changes needed, already correct
- **Modified**: `second_brain/explore_mode.py` — fixed cadence gating (last_check_at → last_suggestion_at)
- **To Update**: OpenClaw cron job payload for `fb47be38-2b39-4372-8e29-052d86dc19cd`

## Expected Behavior After Fix
- Queue worker cron job will execute every 18 million milliseconds (~5 hours)
- Pending queue items will be processed correctly
- No more ImportError crashes
