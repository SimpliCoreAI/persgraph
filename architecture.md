# Distributed Personal AI System — Architecture Document (v1.4)

## 1. System Overview
This system is a distributed personal AI assistant composed of two machines running a multi-agent architecture:

### Mac (Control Plane / Orchestration Layer)
- Runs OpenClaw (primary orchestrator / main agent / router)
- Runs Claude Code (harness — reasoning, code gen, complex tasks)
- Handles:
  - intent classification and task routing
  - sequential harness dispatch and result evaluation
  - re-querying harnesses if results are insufficient
  - Telegram bot interface
  - in-memory task state tracking (max 50 tasks, `deque`)

### Windows (Compute + Memory Layer)
- Runs Ollama + Qwen2.5-72B (LLM inference for all sub-agent work)
- Runs ChromaDB (vector store — all semantic storage)
- Runs Streamlit (internal UI — accessible from Mac browser via Tailscale)
- Provides:
  - high‑performance local LLM inference (privacy-first)
  - embedding generation (nomic-embed-text)
  - semantic search and long‑term memory
  - rich UI dashboard (portfolio, travel, CC agent, tasks, briefing)

The Mac acts as the **brain**, the Windows machine acts as the **muscle + memory + UI**.

---

## 2. Security Model
Security is a primary design requirement. The system must ensure:

- No public exposure of Ollama or ChromaDB
- No LAN exposure
- No router port forwarding
- Only Mac ↔ Windows communication allowed
- All traffic encrypted end‑to‑end

### Security Layers
1. **Tailscale VPN (primary)**
   - Zero‑trust mesh network
   - Encrypted WireGuard tunnel
   - Fixed private IPs (100.x.x.x)
   - No open ports on router or LAN

2. **SSH Server (fallback)**
   - Key‑only authentication
   - No password login
   - Used only if Tailscale unavailable

3. **Localhost or Tailscale‑only binding**
   - Ollama bound to Tailscale IP
   - ChromaDB bound to Tailscale IP

4. **Firewall restrictions**
   - Block LAN access to ports 11434 and 8000
   - Allow only Tailscale subnet (100.0.0.0/8)

---

## 3. Network Topology

```
  User
  ├── Telegram ──────────────────────────────────────────┐
  └── Streamlit (Windows browser) → OpenClaw (Mac) ──────┤
                                                          ▼
                              ┌───────────────────────────────────────┐
                              │                Mac                     │
                              │        OpenClaw (Main Agent)           │
                              │                                        │
                              │  1. Classify intent                    │
                              │  2. Dispatch to harness (sequential)   │
                              │  3. Evaluate result                    │
                              │  4. Requery if needed                  │
                              │  5. Synthesize + respond               │
                              │                                        │
                              │  Harnesses:                            │
                              │  ├── Claude Code (primary)             │
                              │  └── OpenAI Codex (cost fallback)      │
                              │                                        │
                              │  State: in-memory deque (max 50 tasks) │
                              │  Tunnel: Tailscale Encrypted           │
                              └──────────────┬────────────────────────┘
                                             │
                                             ▼
                              ┌───────────────────────────────────────┐
                              │              Windows                   │
                              │      (Compute + Memory + UI)          │
                              │                                        │
                              │  Sub-agents (called by OpenClaw):      │
                              │  ├── RAG Agent (ChromaDB retrieval)    │
                              │  ├── Parser Agent (PDF/CSV parsing)    │
                              │  ├── Memory Agent (ChromaDB R/W)       │
                              │  └── Analysis Agent (Qwen2.5 Ollama)  │
                              │                                        │
                              │  Services:                             │
                              │  ├── Ollama (100.x.x.x:11434)         │
                              │  ├── ChromaDB (100.x.x.x:8000)        │
                              │  └── Streamlit (100.x.x.x:8501)       │
                              └───────────────────────────────────────┘
```

---

## 4. Technical Specification

### 4.1 Core Components
**Mac**
- OpenClaw ✅ running (main agent / router)
- Claude Code (harness — primary)
- OpenAI Codex (harness — cost fallback)

**Windows**
- Ollama + Qwen2.5-72B (all local LLM inference)
- ChromaDB ✅ installed and running (v1.4.4)
- Tailscale ✅ installed and connected
- Streamlit ⬜ planned (internal UI layer)
- Optional SSH server

### 4.2 Multi-Agent Architecture (Phase 1 — Sequential)

#### Main Agent — OpenClaw (Mac)
- Single entry point for all requests (Telegram + Streamlit)
- Classifies intent → selects harness or sub-agent
- Dispatches sequentially (Phase 1), evaluates result, requeries if needed
- Always available while sub-agents are working
- Tracks task state in-memory (`deque`, max 50 tasks, ~8GB Mac safe)
- Synthesizes final response → returns to user

#### Harnesses (Cloud LLMs, called by OpenClaw)
| Harness | Role | Fallback |
|---|---|---|
| Claude Code | Reasoning, code gen, complex analysis | — |
| OpenAI Codex | Code gen alternative | Used if Claude Code cost spikes |

#### Sub-Agents (Local, run on Windows via Tailscale)
| Sub-Agent | Role | Backend |
|---|---|---|
| RAG Agent | Semantic retrieval | ChromaDB + nomic-embed-text |
| Parser Agent | PDF/CSV parsing, transaction extraction | Qwen2.5 via Ollama |
| Memory Agent | Long-term read/write | ChromaDB |
| Analysis Agent | Data analysis, recommendations | Qwen2.5 via Ollama |
| Monitoring Agent | Weekly briefing, system health | Qwen2.5 + external APIs |

#### Request Flow
```
Request (Telegram / Streamlit)
    │
    ▼
OpenClaw — classify intent
    │
    ├──→ Simple query → RAG Agent → ChromaDB → result
    │
    ├──→ Code / reasoning → Claude Code harness → result
    │
    ├──→ Doc parsing → Parser Agent → Qwen2.5 → result
    │
    └──→ Evaluate result
              ├── Good → synthesize → respond
              └── Insufficient → requery same/different agent → respond
```

#### Phase 2 (Future)
- Parallel harness dispatch
- Persistent task store (SQLite)
- Hierarchical sub-agent spawning

### 4.2 Models
**LLMs**
- Qwen2.5‑72B (primary)
- Llama 3 (optional)
- Mistral (optional)

**Embedding Models**
- nomic‑embed‑text (primary)
- snowflake‑arctic‑embed (optional)

### 4.3 RAG Pipeline
- Embedding model: nomic‑embed‑text
- Vector store: ChromaDB
- Retriever: OpenClaw → ChromaDB
- LLM: Qwen2.5‑72B or Claude
- Context injection: OpenClaw

### 4.4 Storage
- ChromaDB stores embeddings + metadata → `C:\chromadb\data`
- Windows stores model files + logs
- Mac stores OpenClaw config + workflows

---

## 5. SSH Server Enablement (Concise Steps)

1. Install OpenSSH Server
2. Start + enable service
3. Allow port 22 in firewall
4. Disable password login
5. Add Mac SSH key
6. Restrict access with `AllowUsers`
7. Restart SSH service
8. Test login from Mac

SSH is now fallback only (Tailscale is primary).

---

## 6. Tailscale VPN Layer (Primary Security)

### Purpose
Provide encrypted, zero‑trust, fixed‑IP connectivity between Mac ↔ Windows.

### Steps
1. Install Tailscale on both devices
2. Log in with same account
3. Verify Tailscale IPs (100.x.x.x)
4. Bind Ollama + ChromaDB to Tailscale IP
5. Restrict access using ACLs
6. Block LAN access via firewall
7. Confirm no router exposure

### Get Tailscale IP on Windows
```powershell
tailscale ip -4
# Returns your 100.x.x.x IP — use this everywhere below
```

### Notes
- Personal plan is free
- 1000‑minute limit applies only to ephemeral devices
- Mac + Windows are persistent → unlimited usage

---

## 7. Binding Ollama to Tailscale IP

### Config file
`C:\Users\<you>\.ollama\config`

Add:

```json
{
  "listen": "100.x.x.x:11434"
}
```

Restart:

```
net stop ollama
net start ollama
```

Verify:

```
netstat -ano | findstr 11434
```

---

## 8. ChromaDB Setup on Windows

### 8.1 Installation

ChromaDB is installed via pip using Microsoft Store Python 3.11.

```powershell
pip install chromadb
```

**Version installed:** `chromadb 1.4.4`

### 8.2 Fix PATH (Microsoft Store Python)

Microsoft Store Python installs CLI tools into a sandboxed path that is not automatically added to PATH. Fix this once:

**Find the Scripts path:**
```powershell
pip show chromadb
# Look at Location: line, Scripts\ is one level up
```

The path will be:
```
C:\Users\<you>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts
```

**Add to PATH permanently** (PowerShell as Admin):
```powershell
$scriptsPath = "C:\Users\$env:USERNAME\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"

[Environment]::SetEnvironmentVariable(
  "Path",
  $env:Path + ";" + $scriptsPath,
  [EnvironmentVariableTarget]::Machine
)
```

Restart PowerShell, then verify:
```powershell
chroma --version
# Should return: chroma 1.4.4
```

### 8.3 Binding ChromaDB to Tailscale IP

Create the data directory and launch ChromaDB bound to the Tailscale IP:

```powershell
# Create persist folder
New-Item -ItemType Directory -Force -Path C:\chromadb\data

# Run bound to Tailscale IP
chroma run --host 100.x.x.x --port 8000 --path C:\chromadb\data
```

Expected output confirms correct binding:
```
Frontend server listening on address, addr: 100.x.x.x:8000
```

> **Important:** ChromaDB must show `100.x.x.x:8000` — not `0.0.0.0:8000`. If it shows `0.0.0.0`, it is exposed on the LAN.

### 8.4 Firewall Rules

Run in PowerShell as **Admin**:

```powershell
# Block all inbound on port 8000
New-NetFirewallRule -DisplayName "Block ChromaDB LAN" `
  -Direction Inbound -Protocol TCP -LocalPort 8000 `
  -Action Block

# Allow only Tailscale subnet (100.0.0.0/8)
New-NetFirewallRule -DisplayName "Allow ChromaDB Tailscale" `
  -Direction Inbound -Protocol TCP -LocalPort 8000 `
  -RemoteAddress "100.0.0.0/8" -Action Allow
```

### 8.5 Verify from Mac

```bash
# Test heartbeat
curl http://100.x.x.x:8000/api/v1/heartbeat
# Expected: {"nanosecond heartbeat": <timestamp>}
```

From Python (OpenClaw side):
```python
import chromadb

client = chromadb.HttpClient(host="100.x.x.x", port=8000)
print(client.heartbeat())
```

### 8.6 Run as Windows Service (Persistent / Auto-start)

> **⚠️ Known Issue — Microsoft Store Python sandbox**
> Windows services (including NSSM) run as SYSTEM or a user account but cannot access Microsoft Store Python packages, which are sandboxed under `C:\Users\<you>\AppData\Local\Packages\...`. Attempts result in `SERVICE_PAUSED` or logon failure even with correct user credentials and "Log on as a service" rights.
>
> **Fix (when ready):** Install Python 3.11 from python.org (not Microsoft Store) → `pip install chromadb` → update NSSM path. ~15 min job.
>
> **Current workaround:** Run ChromaDB manually as needed (see section 8.3).

**When Python is reinstalled from python.org, run these steps:**

Install NSSM:
```powershell
winget install NSSM.NSSM
```

Register ChromaDB as a service:
```powershell
nssm install ChromaDB "C:\Program Files\Python311\Scripts\chroma.exe" `
  "run --host 100.x.x.x --port 8000 --path C:\chromadb\data"

nssm set ChromaDB ObjectName ".\jolly" "<windows-password>"
nssm set ChromaDB Start SERVICE_AUTO_START
nssm set ChromaDB AppStdout C:\chromadb\logs\chroma.log
nssm set ChromaDB AppStderr C:\chromadb\logs\chroma-error.log
nssm start ChromaDB
```

Verify:
```powershell
nssm status ChromaDB
# Expected: SERVICE_RUNNING
```

---

## 9. Hardening Checklist

- [x] Ollama bound to Tailscale IP ✅
- [x] ChromaDB bound to Tailscale IP ✅
- [x] LAN blocked for ports 11434 + 8000 ✅
- [x] Tailscale installed on both devices ✅
- [x] Mac ↔ Windows connectivity verified ✅
- [ ] No router port forwarding
- [ ] SSH key‑only login (fallback)
- [ ] UPnP disabled
- [ ] Windows firewall locked down
- [ ] Mac firewall locked down
- [ ] ChromaDB running as Windows service (auto-start) — blocked by Microsoft Store Python sandbox; fix: reinstall Python from python.org

---

## 10. Streamlit UI Layer (Planned)

Streamlit will run on Windows and serve a unified internal dashboard accessible from Mac browser via Tailscale.

### Access
```
Mac browser → http://100.x.x.x:8501
```

### Firewall rule (when ready)
```powershell
New-NetFirewallRule -DisplayName "Allow Streamlit Tailscale" `
  -Direction Inbound -Protocol TCP -LocalPort 8501 `
  -RemoteAddress "100.0.0.0/8" -Action Allow
```

### Launch
```powershell
streamlit run app.py --server.address 100.x.x.x --server.port 8501
```

### Planned Tabs

| Tab | Description |
|---|---|
| **Portfolio** | Financial analysis, charts (Plotly/Matplotlib) |
| **Learning Agent** | Chat interface backed by ChromaDB + Ollama RAG |
| **Snippets** | Semantic search over personal knowledge base |
| **Travel / POI** | Personal place notes — restaurants, locations, hidden gems |
| **Credit Card Agent** | Statement parsing, rewards optimization, card recommendations |
| **Tasks / Notes** | Capture tasks, appointments, notes — semantically grouped |
| **Weekly Briefing** | Preview and manual trigger for weekly digest |

### Travel / POI Tab — Requirements
- Store: ChromaDB (semantic search over notes)
- Fields: Name, City, Category (restaurant/cafe/market/landmark), Notes, Tags
- Views: By City, By Category
- Query via OpenClaw: "what did I save about Bangalore food?"
- Quick Add form in Streamlit UI

### Credit Card Statement & Points Optimization Agent — Requirements

#### Statement Parsing
- Upload credit card statements (PDF or CSV) via Streamlit UI
- Extract and categorize transactions automatically (dining, travel, groceries, fuel, shopping, etc.)
- Display categorized spend breakdown with charts (Plotly)

#### Rewards Database
- Maintain a local database of card benefits and points structures
- Store: ChromaDB (semantic) + SQLite or JSON (structured card rules)
- Updateable manually via UI — add/edit card benefits, points multipliers, caps
- Fields per card: card name, category multipliers, milestone benefits, expiry rules, annual fee

#### Usage Recommendations
- Analyze transaction history against rewards database
- Suggest optimal card per spend category ("use Card X for dining — 5x points vs 1x on Card Y")
- Identify missed rewards opportunities from past statements
- Highlight upcoming milestone bonuses within reach

#### Privacy
- All processing runs locally on Windows (Ollama LLM + ChromaDB)
- No data sent to external APIs
- Statements stored locally at `C:\chromadb\data\cc_statements\`
- Queryable via OpenClaw: "which card should I use for my flight booking?"

### Tasks / Appointments / Notes — Requirements
- Quick capture via Streamlit UI (minimum required fields to reduce friction)
- Types: Task, Appointment, Note (free-form)
- Minimum fields: Title, Type, Date/Time (optional), Tags (optional), Body
- Store: ChromaDB — embeddings enable semantic grouping ("show everything related to my trip")
- No rigid folder structure — logical groups emerge from semantic similarity
- Queryable via OpenClaw: "what do I have next week?" / "find all notes about investing"
- Design and detailed flow to be finalized during development

### Weekly Briefing Agent — Requirements

#### Schedule
- Fires every **Sunday at 8:00 AM** (scheduled via OpenClaw on Mac)
- Can also be manually triggered from Streamlit (Weekly Briefing tab)

#### Delivery
- **Telegram** — concise summary message
- **Email** — formatted digest (HTML)

#### Content Sections
| Section | Source |
|---|---|
| Next week appointments | ChromaDB (Tasks/Notes store) |
| Upcoming reminders | ChromaDB (Tasks store) |
| Stock earnings (next 4 weeks) | External API (e.g. Finnhub, Alpha Vantage) |
| Expense glimpse (last 7 days) | CC Agent / ChromaDB transactions |
| Quote of the week | Qwen2.5 generated or external API |
| Joke | Qwen2.5 generated |
| System health | Monitoring Agent — ChromaDB status, Ollama uptime, any red flags |

#### System Health Red Flags
- ChromaDB unreachable or slow
- Ollama inference errors
- Mac ↔ Windows Tailscale latency spike
- Any harness failures in the past week

#### Privacy
- All content generated locally (Qwen2.5)
- Only stock earnings data fetches from external API
- Email sent via local SMTP or configured email provider

## 11. Next Steps (Backlog)

**Immediate**
- Install Python 3.11 from python.org (fix NSSM service blocker)
- Set up ChromaDB as Windows service via NSSM
- Install Streamlit on Windows
- Scaffold Streamlit app with all tabs

**Multi-Agent**
- Implement OpenClaw intent classifier + sequential dispatcher
- Build Claude Code harness integration
- Build RAG, Parser, Memory, Analysis sub-agents
- Build Monitoring Agent
- Add OpenAI Codex as cost fallback harness

**Pipelines**
- Build embedding pipeline (nomic‑embed‑text via Ollama)
- Build RAG pipeline (OpenClaw → ChromaDB → Qwen2.5)
- Wire ChromaDB into OpenClaw on Mac

**Features**
- Travel / POI tab (ChromaDB backed)
- Portfolio analysis tab
- Learning agent tab
- Snippets / knowledge base tab
- Credit Card Agent tab (statement parsing, rewards DB, usage recommendations)
- Tasks / Appointments / Notes tab (semantic store, ChromaDB)
- Weekly Briefing Agent (Sunday 8AM, Telegram + Email delivery)
- File/photo indexing

**Ops**
- Fix Mac sleep issue (caffeinate / Power Nap — keeps OpenClaw responsive)
- Automated backups for ChromaDB
- Monitoring / logging layer
- UPnP disabled on router
- SSH key‑only fallback configured

**Phase 2 (Future)**
- Parallel harness dispatch
- Persistent task store (SQLite)
- Streamlit direct → Windows reads for latency-sensitive tabs
