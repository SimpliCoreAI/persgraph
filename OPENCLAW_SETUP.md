# 🦞 OpenClaw Setup Guide

Get OpenClaw running and connected to this repo in ~15 minutes.

> Based on the [OpenClaw on Mac Mini: The Complete Setup Guide](https://open.substack.com/pub/robertheubanks/p/openclaw-on-mac-mini-the-complete) by Robert Heubanks — the most complete community reference available.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| macOS | Sequoia / Sonoma | Apple Silicon or Intel |
| Node.js | **24+** (recommended) | [nodejs.org](https://nodejs.org) — use nvm for version management |
| npm | 10+ | Comes with Node |
| Git | any | [git-scm.com](https://git-scm.com) |
| Password manager | — | Apple Keychain, Bitwarden, or 1Password |

---

## Phase 0 — Credentials (do this first)

Get all API keys before touching the install. You'll need:

### LLM Provider (required — pick one)
- **Anthropic API key** → [console.anthropic.com](https://console.anthropic.com) *(recommended — Claude Sonnet/Opus)*
- **OpenAI API key** → [platform.openai.com](https://platform.openai.com) *(alternative)*

⚠️ **Set a monthly spending cap ($20–50) before you generate the key.** A misconfigured heartbeat can burn credits fast.

### Web Search (recommended — pick one)
| Provider | Get key at | Notes |
|----------|-----------|-------|
| **Brave** *(default)* | [brave.com/search/api](https://brave.com/search/api/) | Free tier, OpenClaw default |
| **Perplexity** | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) | AI-synthesized answers; use model `sonar-pro` |
| **Exa** | [exa.ai](https://exa.ai/) | Neural search, better research quality; needs custom skill |

### Google Account (for Gmail / Calendar / Drive)
Create or dedicate a Gmail account for OpenClaw infrastructure:
- Suggested pattern: `yourname-openclaw@gmail.com`
- Enable 2FA: [myaccount.google.com/security](https://myaccount.google.com/security)
- This is NOT the address you'll send email from — it's for OAuth/system use only

### Telegram Bot (for chat interface)
1. Open Telegram → search **@BotFather** (look for blue checkmark)
2. `/newbot` → pick a display name (e.g. "Atlas", "Friday")
3. Pick a username ending in `bot` (e.g. `myagent_bot`)
4. **Copy the token immediately** — looks like `7123456789:AAF1x2y3...`
5. Save it to your password manager — shown only once

### Discord Bot (optional)
1. [discord.com/developers/applications](https://discord.com/developers/applications) → New Application
2. Bot → Reset Token → copy immediately
3. Enable **Message Content Intent** and **Server Members Intent**
4. Save token to password manager

---

## Phase 1 — Install Node.js + OpenClaw

```bash
# Install nvm (Node version manager) — recommended
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.zshrc

# Install Node 24 (recommended for OpenClaw)
nvm install 24
nvm use 24
nvm alias default 24

# Verify
node --version   # should show v24.x.x
npm --version
```

```bash
# Install OpenClaw globally
npm install -g openclaw

# Verify
openclaw --version
```

---

## Phase 2 — Run the Setup Wizard

```bash
openclaw setup
```

The interactive wizard will ask for:
1. **LLM provider** → paste your Anthropic or OpenAI API key
2. **Google auth** → sign in with your `-openclaw@gmail.com` account when browser opens
3. **Web search** → paste your Brave (or Perplexity) API key
4. **Telegram** → paste your bot token
5. **Discord** → paste your bot token (or skip)
6. **Gateway token** → auto-generated, save it
7. **Hooks** → enable boot, command logger, session memory hooks when offered

---

## Phase 3 — Start the Gateway

```bash
openclaw start
```

Verify it's running:
```bash
openclaw status
```

OpenClaw runs as a persistent background service. On macOS it registers a LaunchAgent so it restarts on reboot.

---

## Phase 4 — Connect to this Repo

Set the workspace to PersGraph:

```bash
openclaw config set workspace ~/AgenticHub/Persgraph
```

Or edit `~/.openclaw/config.json` directly and set:
```json
{
  "workspace": "~/AgenticHub/Persgraph"
}
```

Restart after config changes:
```bash
openclaw restart
```

---

## Phase 5 — Configure Workspace Files

OpenClaw reads these files from the workspace root on every session. Customize them:

| File | Purpose |
|------|---------|
| `SOUL.md` | Agent personality and hard rules |
| `IDENTITY.md` | Agent name, emoji, avatar |
| `USER.md` | Info about you — name, timezone, preferences |
| `AGENTS.md` | Behavioral guidelines, tool notes, memory conventions |
| `MEMORY.md` | Long-term memory (main session only — keep private) |
| `HEARTBEAT.md` | Periodic check checklist |
| `TOOLS.md` | Environment-specific notes (SSH hosts, device names, etc.) |

Templates for all seven are in Appendix E of the [community guide](https://open.substack.com/pub/robertheubanks/p/openclaw-on-mac-mini-the-complete). This repo already has them — edit to personalize.

---

## Phase 6 — Heartbeat (proactive check-ins)

Add to `~/.openclaw/config.json` under `agents.defaults`:

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "enabled": true,
        "every": "30m",
        "model": "anthropic/claude-3-5-haiku-20241022"
      },
      "compaction": {
        "memoryFlush": true
      }
    }
  }
}
```

> **Model tip:** Use Haiku for heartbeat — it's 20x cheaper than Sonnet and handles periodic checks fine.

---

## Phase 7 — gog (Google Workspace CLI)

For Gmail, Calendar, Drive, Contacts:

```bash
npm install -g @openclaw/gog

# Authenticate
gog auth login --account yourname-openclaw@gmail.com
```

Enable these APIs in [Google Cloud Console](https://console.cloud.google.com) for your project:
- Gmail API
- Google Calendar API
- Google Drive API
- Google Contacts API
- Google Docs API *(optional)*
- Google Sheets API *(optional)*

Verify auth:
```bash
gog gmail list --account yourname-openclaw@gmail.com
```

---

## Phase 8 — Security Hardening

### Firewall
```
System Settings → Network → Firewall → Turn On
```
Do **not** enable "Block all incoming connections" if you use Tailscale or SSH — it silently breaks both.

Verify SSH is allowed after enabling:
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getappblockall
```

### Standard User Account (recommended)
Create a dedicated standard (non-admin) account for OpenClaw to run under. Limits blast radius if anything goes wrong.

### Config file permissions
```bash
chmod 600 ~/.openclaw/config.json
chmod 600 ~/.openclaw/credentials/oauth.json
```

### Workspace plugin security
When installing skills from ClawHub, OpenClaw v2026.1.29+ requires explicit approval. Never auto-load workspace plugins from untrusted sources.

---

## Phase 9 — Useful Slash Commands

| Command | What it does |
|---------|-------------|
| `/status` | System status, token usage, active sessions |
| `/new` | Start a fresh session (fires session-memory hook) |
| `/compact` | Compact context window |
| `/think` | Toggle extended thinking mode |
| `/set model <name>` | Override model for current session |
| `/memory` | View/search memory |
| `/models` | List available models |
| `/restart` | Restart the gateway |
| `/approve` | Approve a pending elevated action |

---

## Phase 10 — Outbound Email (optional)

If you want OpenClaw to send email as you (not the infra account):
- Create a second Gmail: `firstname.lastname@gmail.com`
- Authenticate it separately: `gog auth login --account firstname.lastname@gmail.com`
- This is the address recipients see

---

## Key Directories

| Path | Contents |
|------|---------|
| `~/.openclaw/` | Gateway config, credentials, session data |
| `~/.openclaw/config.json` | Main config file |
| `~/.openclaw/credentials/oauth.json` | Google OAuth tokens |
| `~/.openclaw/workspace/` | Default workspace (overridden by config) |
| `~/AgenticHub/Persgraph/` | This repo — your actual workspace |

Environment variable overrides:
```bash
OPENCLAW_HOME=~/.openclaw          # config/data root
OPENCLAW_WORKSPACE=~/path/to/repo  # workspace override
```

---

## Troubleshooting

**Gateway won't start**
```bash
openclaw status
openclaw restart
# Check logs:
tail -f ~/.openclaw/logs/gateway.log
```

**Telegram bot not responding**
- Check bot token in config: `openclaw config get`
- Make sure you started a conversation with the bot on Telegram (bots can't initiate)
- Verify gateway is running: `openclaw status`

**Google auth failing**
- Re-run: `gog auth login --account yourname-openclaw@gmail.com`
- Check API enablement in [Google Cloud Console](https://console.cloud.google.com)
- Check OAuth consent screen is configured

**Heartbeat not firing**
- Confirm `every` not `interval` in config (breaking change in older versions)
- Confirm nesting under `agents.defaults.heartbeat`

**Context compaction losing memory**
- Enable `memoryFlush: true` under `agents.defaults.compaction`
- Consider the [lossless-claw](https://github.com/openclaw/lossless-claw) plugin (recommended by Pete Steinberger for solving context loss)

---

## Helpful Resources

- [OpenClaw Docs](https://docs.openclaw.ai)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [Community Setup Guide (Mac Mini)](https://open.substack.com/pub/robertheubanks/p/openclaw-on-mac-mini-the-complete) — most complete reference
- [Matthew Berman's deep dive](https://www.youtube.com/watch?v=Q7r--i9lLck)
- [Ray Fernando's 4-hour livestream](https://www.youtube.com/watch?v=7UmXs3z3Hks)
- [trust.openclaw.ai](https://trust.openclaw.ai) — security program
- [migration guide](https://docs.openclaw.ai/migration)
