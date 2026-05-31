# SwarmForge AI — Product Vision Doc
*Draft v0.1 — May 25, 2026 — Refine in morning*

---

## What Is It?

A **Super Agent platform for small businesses** that connects to their social accounts (Twitter/X, Instagram, Facebook), understands their brand and audience, and autonomously spawns specialized sub-agents to find leads and generate income — with the human always in control.

Not another chatbot. Not another scheduling tool. An AI workforce that *learns your business* before it acts.

---

## The Core Problem

Small business owners are the bottleneck in their own growth:
- Too busy to post consistently
- No system to find and qualify leads
- Can't afford a marketing team
- Existing AI tools are generic — they don't know *your* brand

**The gap:** No product today reads an existing business's social presence, understands their voice and audience, and autonomously hunts for leads — all in one connected flow.

---

## Product Architecture

### The Super Agent (Always Included)
The brain. Interviews the owner, builds the business profile, monitors performance, and recommends which agents to add based on real data. Lives outside any subscription tier.

### Sub-Agents (Subscription-Based)
Specialized workers spun up based on the business's goals:

| Agent | Function |
|---|---|
| **Analyzer Agent** | Audits social accounts, extracts brand voice, maps opportunities |
| **Content Agent** | Drafts posts in brand voice, queues for approval |
| **Lead Scout Agent** | Monitors keywords, flags ICP accounts, builds prospect lists |
| **Scheduler Agent** | Posts at optimal times, manages content calendar |
| **Outreach Agent** | Drafts DMs/replies, holds for explicit human approval |
| **Tracker Agent** | Measures results, generates weekly reports, suggests upsells |

---

## Onboarding: Business Clarification Wizard

**Key differentiator — no competitor does this.**

Instead of a form, the Super Agent conducts a structured conversation:

1. *"What do you sell?"* → Product/service type
2. *"Who's your ideal customer?"* → ICP definition
3. *"Which platforms are you active on?"* → Connect socials
4. *"What's your #1 goal right now?"* → Leads / Sales / Brand / All
5. *"Any competitors you admire?"* → Benchmark targets
6. *"What's your monthly budget comfort?"* → Agent tier suggestion

**Output:** A **Business Overview Card** the owner reviews, edits, and approves before any agents activate. Human confirms the AI's understanding before anything runs.

This builds trust from the first interaction.

---

## Human-in-the-Loop Design

Three action levels, adjustable per agent:

| Level | Examples | Default |
|---|---|---|
| 🟢 **Auto** | Research, analysis, drafting, internal reports | Always on |
| 🟡 **Notify** | Content ready to post, lead list compiled | Approve in-app |
| 🔴 **Explicit Approve** | Sending DMs, going live, any spend | One-tap required |

Starts conservative. User loosens autonomy as trust builds. Full audit log of every action.

---

## Subscription Model — Agent-Based Tiers

| Tier | Agents | Price/mo | Target |
|---|---|---|---|
| **Starter** | Analyzer + Content | $29 | Just getting started |
| **Growth** | + Lead Scout + Scheduler | $79 | Active small biz |
| **Pro** | + Outreach + Tracker | $149 | Scaling fast |
| **Custom** | À la carte | $29/agent | Power users |

**Super Agent always included** — it's the brain, not a feature.

### Super Agent as Smart Upsell Engine
Recommendations are data-driven, not generic:
> *"Your content is getting 3x more engagement this month. I found 47 potential leads commenting on competitor posts — but Lead Scout isn't active. Add it for $29/mo?"*

---

## Competitive Landscape

| Product | What They Do | Their Gap |
|---|---|---|
| ManyChat | Instagram/FB DM automation | No intelligence, just flow builders |
| Chatfuel | WhatsApp/Instagram bots | Template-driven, no AI reasoning |
| Apollo.io | B2B lead database + outreach | No social listening, enterprise-only |
| Lindy AI | General AI sales agents | Not social-native |
| Respond.io | Inbound chat qualification | Reactive, not proactive |
| SwarmForge | Vision/pitch (thin MVP) | Vague "super-swarm", no real product |

**Our edge:** Brand-aware, onboarding-first, agent economy model, human trust built in from day one.

---

## Key Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Meta API restrictions (IG/FB DMs) | 🔴 High | Start read-only; DMs in v2 after Meta partnership |
| Twitter/X API cost | 🟡 Medium | Pass cost into tier pricing; start with free tier limits |
| Account ban risk | 🔴 High | No aggressive automation; all outreach requires approval |
| SMB trust gap | 🟡 Medium | Clarification wizard + conservative defaults builds trust |
| Legal (CAN-SPAM, GDPR) | 🔴 High | All outreach explicit-approve only; no cold DM blasts |

---

## Build Order (MVP)

1. **Business Clarification Wizard** — UI + SuperAgent prompt (build first, core differentiator)
2. **Social Analyzer** — Twitter/X read-only audit (safest API to start)
3. **Content Drafter** — generates posts in brand voice, human approves
4. **Results Tracker** — engagement metrics + weekly summary
5. **Stripe Billing** — agent-based subscription tiers
6. **Lead Scout + Outreach** — v2 after trust and traction

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | OpenClaw + Claude (deep thinking for strategy) |
| Sub-agents | Claude Sonnet / lower cost models for routine tasks |
| Social APIs | Twitter/X API, Instagram Graph API, Facebook Pages API |
| Frontend | React / Next.js (wizard UI) |
| Billing | Stripe |
| Memory/Context | ChromaDB (per-business vector store) |
| Hosting | TBD |

---

## Next Steps (Morning)
- [ ] Refine this doc
- [ ] Build wizard UI mockups / user flow
- [ ] Decide: start with Twitter/X only or multi-platform from day one?
- [ ] Research Meta Business Partner requirements for IG DMs
- [ ] Define the Business Overview Card format

---

*Generated from product discussion — May 25, 2026*
