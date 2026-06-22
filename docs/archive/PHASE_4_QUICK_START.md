# Phase 4 Quick Start — Streamlit Dashboard

**Status:** ✅ READY FOR USE  
**Version:** 0.4.0  
**Type:** NEW UI (not archived)

---

## 30-Second Quickstart

```bash
cd /root/AgenticHub/Persgraph
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py
```

Then open: http://localhost:8501

---

## Installation

### Requirements

- Python 3.12+
- Streamlit 1.28+
- Pandas 2.0+

### Check if Already Installed

```bash
cd /root/AgenticHub/Persgraph
.venv/bin/python -c "import streamlit, pandas; print(f'OK: streamlit {streamlit.__version__}, pandas {pandas.__version__}')"
```

### Install (if needed)

```bash
cd /root/AgenticHub/Persgraph
.venv/bin/pip install streamlit pandas
```

---

## Running the Dashboard

### Local (Development)

```bash
cd /root/AgenticHub/Persgraph
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py
```

**Output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
  
  To stop this server, press Ctrl + C
```

### Remote Server

```bash
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py \
  --server.port 8501 \
  --server.address 0.0.0.0
```

Then visit: `http://your-server-ip:8501`

---

## Dashboard Pages

### 1. 📊 Overview

**What it shows:**
- Today's total cost
- Number of operations
- Total tokens used
- Top command (by cost)

**When to use:**
- Quick daily cost check
- Spot highest-cost operation

**Example:**
```
Today's Cost: $2.45
Operations: 42
Total Tokens: 150,234
Top Command: ask ($1.20)
```

### 2. 📈 Summaries

**What it shows:**
- Costs grouped by dimension (command, user, layer, model, date, trigger)
- Date range filtering
- Detailed table with cost, count, avg cost, token count
- Summary statistics
- Export to CSV/JSON/Markdown

**When to use:**
- Analyze costs by any dimension
- Export for reports or spreadsheets
- Compare costs across groups

**Example Workflow:**
1. Select "command" in dropdown
2. Set start_date to 7 days ago, end_date to today
3. Review table (sorted by cost)
4. Click "Download Markdown" for email report

### 3. 🔍 Event Details

**What it shows:**
- Event IDs for each group
- Expandable rows (click to see full list)
- Copy-paste helper for event IDs
- How to use event IDs for debugging

**When to use:**
- Link to specific cost-driving events
- Find Langfuse traces for detailed debugging
- Audit trail for feedback loops

**Example Workflow:**
1. Expand "ask" command row
2. See 25 event IDs
3. Copy first 5 event IDs
4. Paste in Langfuse UI to find traces
5. Debug cost drivers, latency, errors

### 4. ⚠️ Alerts

**What it shows (3 tabs):**

**a) Anomalies (Cost Spikes)**
- Detected anomalies (>2σ above baseline)
- Severity (low/medium/high)
- User/operation/cost breakdown
- Baseline comparison

**b) New Operations**
- Operations never seen before
- Early warning for new commands

**c) Spending Summary**
- By-user total costs
- By-operation total costs
- Informational only

**When to use:**
- Monitor for cost spikes
- Get early warning for new operations
- Review overall spending

**Example Workflow:**
1. Go to "Alerts" tab
2. Select "anomaly" in dropdown
3. See all cost spikes from last 7 days
4. Click an anomaly to see details

### 5. ℹ️ Help

**What it shows:**
- Dashboard overview
- Feature descriptions
- Common tasks (5 step-by-step walkthroughs)
- Data freshness expectations
- Links to documentation
- FAQ

**When to use:**
- First time learning dashboard
- Stuck on a common task
- Need to understand a feature

---

## Common Tasks

### Task 1: View Today's Costs by Operation

**Steps:**
1. Open dashboard → "Summaries" page
2. Dropdown: Select "command"
3. Date range: Set both to today
4. Click "Refresh"

**What you'll see:**
Table with all operations (ask, ingest, query, etc.) and their costs.

**Example output:**
```
| Group | Total Cost | Count | Avg Cost | Tokens |
|-------|-----------|-------|----------|--------|
| ask   | $1.20     | 15    | $0.080   | 2,500  |
| ingest| $0.45     | 5     | $0.090   | 1,200  |
| query | $0.30     | 8     | $0.038   | 800    |
```

### Task 2: Export Weekly Cost Report (Email)

**Steps:**
1. Go to "Summaries" page
2. Select grouping: "command" (or your preferred dimension)
3. Date range:
   - Start: 7 days ago (e.g., 2026-06-13)
   - End: today (2026-06-20)
4. Click "Download Markdown"
5. Save file, open in editor, copy/paste into email

**What you'll get:**
```markdown
# Cost Summary Report

## By Command

| Command | Total Cost | Operations | Avg Cost |
|---------|-----------|-----------|----------|
| ask     | $8.50     | 95        | $0.0895  |
| ingest  | $2.10     | 12        | $0.1750  |

## Statistics
- Total Cost: $10.60
- Total Operations: 107
- Avg per Operation: $0.0991
```

### Task 3: Find Cost Anomalies

**Steps:**
1. Go to "Alerts" page
2. Select "anomaly" in dropdown
3. Set lookback_days to 7 (baseline window)
4. Click "Refresh"

**What you'll see:**
List of cost spikes with:
- User ID
- Operation
- Today's cost vs. baseline
- Severity (low/medium/high)

**Example:**
```
⚠️ HIGH | user_123 / ask
Today: $0.45 | Baseline: $0.08
Reason: 3.2σ above average
```

### Task 4: Debug Specific Cost Events

**Steps:**
1. Go to "Event Details" page
2. Select grouping: "command" (to group by operation)
3. Expand a group (e.g., "ask")
4. Copy first 5 event IDs
5. Go to Langfuse UI
6. Paste event ID in search bar
7. Review trace details (latency, tokens, errors)

**Event ID example:**
```
evt_2026_06_20_ask_1
evt_2026_06_20_ask_2
evt_2026_06_20_ask_3
```

### Task 5: Review Overall Spending

**Steps:**
1. Go to "Alerts" page
2. Select "summary" in dropdown
3. Review "By User" table
4. Review "By Operation" table

**What you'll see:**
Aggregated costs by dimension for quick overview.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Reload dashboard (F5) |
| ↑/↓ | Scroll table |
| `Ctrl+S` | Save/export (browser native) |
| `Ctrl+C` | Stop dashboard (terminal) |

---

## Troubleshooting

### "Streamlit not found"

**Error:**
```
ModuleNotFoundError: No module named 'streamlit'
```

**Fix:**
```bash
cd /root/AgenticHub/Persgraph
.venv/bin/pip install streamlit pandas
```

### "Cost Agent not available"

**Error:**
```
Cost Agent not available. Check PYTHONPATH and imports.
```

**Fix:**
```bash
# Make sure you're in the right directory
cd /root/AgenticHub/Persgraph

# Make sure PYTHONPATH is set
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py
```

### "No cost data available"

**Possible causes:**
1. Phase 1 poller hasn't run yet
2. Cost files are empty
3. Langfuse has no data

**Check:**
```bash
ls -la /root/AgenticHub/Persgraph/data/cost_*.json

# Should see:
# cost_agent_state.json
# cost_by_user.json
# cost_by_operation.json
# etc.
```

**Fix:**
1. Wait for Phase 1 poller to run (typically 5 min)
2. Run `/ask` command to generate cost
3. Check Langfuse integration is working

### Dashboard loads slow

**Possible causes:**
1. Large date range (lots of data)
2. Network latency to Langfuse
3. Computer is slow

**Fix:**
1. Try shorter date range (last 1-2 days)
2. Click "Refresh" to reload
3. Close other apps

---

## Data Freshness

**Question:** How up-to-date is the data?

**Answer:**
- Phase 1 poller runs every 5 minutes (typically)
- Dashboard reads files immediately
- **Latency:** Usually < 5 minutes behind real costs

To refresh: Click "Refresh" button (any page)

---

## Tips & Tricks

### Tip 1: Export for analysis

Use CSV export to analyze in Excel/Google Sheets:

1. Summaries → command grouping → date range → Download CSV
2. Open in Excel
3. Create pivot tables, charts, etc.

### Tip 2: Find expensive events

Use Event Details drill-down:

1. Event Details → command grouping → expand group
2. Copy event IDs
3. Paste in Langfuse search
4. Check latency, tokens, errors

### Tip 3: Monitor for spikes

Set a daily reminder to check Alerts page:

1. Alerts → anomaly
2. Look for "HIGH" severity
3. Investigate immediately

### Tip 4: Compare periods

Use Summaries with date range:

1. Summaries → command grouping → set date range (week 1)
2. Download Markdown
3. Change date range (week 2)
4. Download Markdown again
5. Compare in spreadsheet

---

## Performance Tips

### Speed Up Page Load

1. Use **shorter date ranges** (1-7 days instead of 30 days)
2. Select **specific grouping** (command) instead of large groups (worker)
3. Click "Refresh" only when needed

### Save Bandwidth

1. Download **CSV** instead of JSON (smaller)
2. Use **Markdown** for reports (human-readable, compact)

### Reduce Memory

1. Close unused browser tabs
2. Close other apps
3. Restart dashboard periodically (weekly)

---

## Common Questions

### Q: Is my data safe?

**A:** YES. Dashboard is **read-only**:
- ✅ No writes to cost files
- ✅ No risk of data corruption
- ✅ Safe to use while poller runs

### Q: Can multiple people use the dashboard?

**A:** YES. For team use:

Option 1: Share the server URL
```bash
# On shared server
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py \
  --server.address 0.0.0.0 \
  --server.port 8501
# Share URL: http://server-ip:8501
```

Option 2: Run separate instances on different ports
```bash
# Terminal 1 (port 8501)
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py --server.port 8501

# Terminal 2 (port 8502)
PYTHONPATH=. streamlit run agents/cost_agent/ui_streamlit.py --server.port 8502
```

### Q: Can I customize the dashboard?

**A:** YES. Edit `ui_streamlit.py`:
- Change colors, fonts, styling
- Add new pages
- Modify export formats
- Add custom filters

See PHASE_4_IMPLEMENTATION.md for details.

### Q: How do I export data for BI tools?

**A:** Use JSON export:

1. Summaries → Select grouping + date range
2. Download JSON
3. Import into:
   - Power BI
   - Tableau
   - Metabase
   - Google Data Studio
   - Custom Python scripts

### Q: Can this replace my existing cost reports?

**A:** MAYBE. Depends on your use case:

✅ **Suitable for replacing:**
- Excel cost summaries
- Email cost reports
- Manual analysis

❌ **NOT suitable for replacing:**
- Automated invoice generation
- Multi-company billing
- Detailed cost allocation rules (Phase 5 feature)

---

## Getting Help

### Documentation

- **Quick start:** This file
- **Implementation details:** PHASE_4_IMPLEMENTATION.md
- **API reference:** PHASE_3_QUICK_START.md
- **Roadmap:** PHASE_ROADMAP.md

### Common Issues

1. Check "Help" page in dashboard
2. Review troubleshooting section above
3. Check error messages in browser console (F12)

### Report Issues

- Check Phase 4 implementation doc
- Review cost agent logs
- Verify Langfuse integration is working

---

## Keyboard Cheat Sheet

| Scenario | Action |
|----------|--------|
| Refresh data | Click "Refresh" button |
| Export CSV | Click "Download CSV" button |
| Stop dashboard | Press Ctrl+C in terminal |
| View help | Click "ℹ️ Help" page |
| Change date range | Drag date picker or click |

---

## Next Steps

1. ✅ Run the dashboard: `streamlit run agents/cost_agent/ui_streamlit.py`
2. ✅ Explore each page (Overview, Summaries, Events, Alerts, Help)
3. ✅ Try one export (CSV, JSON, or Markdown)
4. ✅ Check Event Details for event IDs
5. ⏳ Bookmark the dashboard for daily use

---

## Version Info

- **Phase:** 4 (Streamlit Dashboard)
- **Version:** 0.4.0
- **Status:** READY FOR USE
- **Last Updated:** 2026-06-20

---

**Ready to explore your costs! 💰**
