# Scratchpad: Medium Article — The PersGraph Journey

**Status:** active
**Created:** 2026-06-07
**Last updated:** 2026-06-07
**Advisor:** claude-sonnet-4-6
**Executor:** gpt-4o (draft) / claude-haiku-4-5 (checks)

---

## Goal
Write a Medium article about how ingestion/ask evolved into a full personal agent (PersGraph), covering:
- The origin story (small, useful, focused)
- How the system helped improve itself
- Key engineering incidents and lessons
- The scratchpad/transient memory workflow as a highlight or separate piece
- Practical lessons for other builders

## Context
- PersGraph started as a personal knowledge base: ingest URLs, notes, PDFs → ask questions
- Grew into a full personal agent with: Langfuse tracing, email workflows, travel planner, morning briefing, multi-user family KB, slash commands via Telegram
- Hosted on VPS (DigitalOcean), Caddy HTTPS, Flask app, ChromaDB on Andromeda
- Today's session was a live example of the agent helping improve itself:
  - Fixed login loop (Flask session cookies behind Caddy)
  - Fixed Langfuse host (localhost → cloud)
  - Scrubbed secrets from public repo (.env gitignored)
  - Recovered corrupted scripts/command.py
  - Updated README + marketing page
  - Built transient scratchpad workflow as a reusable skill

## Decisions made
- Write as **journey + case study**, not a product announcement
- Two articles, not one:
  1. "How ingestion/ask evolved into a full personal agent"
  2. "Scratchflow: the transient scratchpad that keeps models in sync"
- Tone: practical, slightly personal, confident — not salesy, not corporate
- Target length: 1,200–1,800 words each
- Audience: builders, devs, AI tinkerers

## Open questions
- Should article 1 include a teaser for Scratchflow or leave it fully separate?
- Is there a screenshot or diagram that would illustrate the architecture?
- Does the article go on Jolly's personal Medium or a publication?
- Which screenshots best establish a strong first impression?
- Where should GitHub links be placed so they support credibility without distracting from the narrative?

## Next actions
- [x] Capture context in scratchpad
- [x] Write draft article in scratchpad
- [ ] Jolly reviews draft
- [ ] Add screenshot placements and GitHub link strategy to Article 1
- [ ] Handoff to GPT for rewrite/polish if needed
- [ ] Jolly approves final
- [ ] Publish to Medium

## Handoff notes
- Advisor (Claude/Sonnet): advise on narrative structure, tone, where to cut, and where to place screenshots/GitHub links
- Executor (GPT): rewrite for polish and Medium-appropriate flow
- Reviewer: Jolly

## Completion criteria
- Two polished drafts ready for Medium
- At least one has been reviewed and approved by Jolly
- Email sent with draft copy

---

## Draft: Article 2 — Scratchflow

# Scratchflow: The Transient Memory Layer That Keeps My AI Models in Sync

*Why I stopped writing working thoughts into long-term memory and built a scratchpad instead.*

---

I used to treat memory like a bucket.

If I had an idea, a debugging trail, a prompt pattern, or a draft article, I’d dump it into long-term memory and hope I could find it later. That works for a while — until it doesn’t. Long-term memory gets noisy. Notes become stale. Drafts blur into decisions. And the thing you actually needed to remember gets buried under everything else.

That’s why I built Scratchflow.

Scratchflow is my transient memory layer: a scratchpad for active thinking, model handoffs, and work-in-progress context. It’s not a knowledge base. It’s not a second brain. It’s not where I store durable facts. It’s the place where the models and I coordinate while something is still in motion.

---

## Why build it at all?

Because not all context deserves to become memory.

A lot of AI workflows collapse because they treat every intermediate thought as if it should be permanent. But active work needs a different shape. You need somewhere to put:

- the current goal
- the latest decision
- the unresolved question
- the next action
- the handoff to the next model

Without that, you end up repeating yourself, overloading long-term memory, or feeding a model too much irrelevant history.

Scratchflow solves that by keeping the workbench separate from the archive.

---

## The problem it solves

Scratchflow was built to address four practical problems:

**1. Prompt sprawl**
Long prompts get repetitive fast. Once you’ve explained the same topic three times, the quality drops. A scratchpad gives the model a stable context object to work from.

**2. Model handoff friction**
Claude is great at critique and architecture. GPT is great at drafting. Haiku is great at execution. But if each model has to rediscover the whole topic from scratch, you lose the advantage of specialization.

**3. Memory pollution**
If you write every idea into durable memory, the important stuff gets mixed with the temporary stuff. Scratchflow keeps working notes out of `MEMORY.md` unless they become truly durable.

**4. Multi-step work drift**
Long tasks drift when the next step isn’t explicit. Scratchflow keeps the next action visible.

---

## How Scratchflow is structured

I built it as a small, explicit workflow:

- `scratchpad/README.md` — what it is and how to use it
- `scratchpad/template.md` — the note structure
- `scratchpad/prompts.md` — the exact invocation prompts
- `scratchpad/active/` — live topics
- `scratchpad/handoff/` — summaries for another model
- `scratchpad/closed/` — completed topics

A scratchpad note usually has:

- Goal
- Context
- Decisions made
- Open questions
- Next actions
- Handoff notes
- Completion criteria
- Log

That sounds simple because it is. Simplicity is the feature.

---

## Why this is better than just more memory

The biggest advantage is separation of concerns.

Long-term memory should be curated. It should hold things like:
- stable preferences
- repeated decisions
- durable facts
- architecture choices that matter over time

Scratchflow holds the messy middle:
- brainstorming
- draft outlines
- unresolved tradeoffs
- temporary plans
- model-specific instructions

If the scratchpad becomes useful enough to keep, you distill it later. If not, you close it and move on.

That’s the difference between a memory system and a working system.

---

## Architectural advantages

Scratchflow gives me a few nice properties:

**1. It’s model-agnostic**
Any model can read a scratchpad and continue the work.

**2. It’s explicit**
The scratchpad makes the current state visible instead of hidden inside chat history.

**3. It reduces context waste**
The model gets a concise working summary instead of a mountain of old messages.

**4. It improves handoffs**
One model can advise, another can draft, another can execute — all from the same transient state.

**5. It keeps the main memory clean**
That matters more than it sounds. Clean memory is easier to trust.

---

## Tradeoffs and disadvantages

Scratchflow isn’t free.

**1. It adds another thing to maintain**
Any workflow layer adds overhead. You have to decide when to start, update, hand off, and close.

**2. It can become a junk drawer**
If you don’t enforce the rules, the scratchpad becomes the new memory dump.

**3. It’s not automatic**
The system only works if you use it consistently.

**4. It can duplicate some chat history**
That’s okay, but it means the note must stay concise or it becomes noisy.

So the point isn’t to replace memory. The point is to keep temporary work temporary.

---

## Prompt examples

These are the prompts I actually want to use.

**Start a scratchpad**
> Start a scratchpad for `<topic>`. Keep it transient, model-agnostic, and separate from MEMORY.md. Capture goal, context, decisions, open questions, next actions, and handoff notes. Do not promote anything to long-term memory.

**Update a scratchpad**
> Update the scratchpad for `<topic>` with this new context: `<paste>`. Keep the scratchpad concise. Preserve decisions, add open questions, and update next actions. Do not write to MEMORY.md.

**Handoff to another model**
> Handoff the scratchpad for `<topic>` to `<model>`. Summarize current context, decisions, and the exact next actions. Keep it short and actionable. Do not rewrite history.

**Close a scratchpad**
> Close the scratchpad for `<topic>`. Summarize final outcome, decisions, and any durable lessons. Mark the scratchpad as closed and do not keep raw working notes unless explicitly requested.

**Use it as transient memory**
> Use the scratchpad as transient memory for this task. Treat MEMORY.md as off-limits unless something becomes durable and worth curating. Keep the scratchpad concise and update it as the source of truth for this topic.

---

## Why the name Scratchflow?

Because it’s not just a file. It’s a flow.

The goal is to make transient thinking move cleanly through a system:
- start with context
- work in the scratchpad
- hand off between models
- close when done
- archive only if useful

That’s the whole idea.

---

## Where it fits in the larger system

Scratchflow is part of the same philosophy that shaped PersGraph itself:

- start small
- keep things useful
- make the system debuggable
- prefer clean interfaces over cleverness
- let the assistant help maintain itself

That’s the real theme of the whole project.

---

## Closing thought

A good AI system shouldn’t force every thought into permanent memory.

Some thoughts are working thoughts.
Some are drafts.
Some are handoffs.
Some are disposable.

Scratchflow is how I keep those layers separated.

And that turns out to make the whole system more usable, more trustworthy, and a lot easier to work with.

---

*If you’re building your own personal agent, don’t just add memory. Add a place for thought in progress.*

---

## Article 1 guidance
- Open with a strong hook that frames PersGraph as a useful system that evolved into a self-maintaining personal agent
- Reserve space for 1–3 screenshots from the PersGraph website early in the article (hero section, dashboard, or action flow)
- Include GitHub links from the marketing HTML as credibility anchors, but keep them secondary to the story
- Aim for a first-impression structure: hook → visual proof → origin story → growth → self-healing session → lessons learned → next step
- Keep the story gradual: ingest/ask first, then best practices, then tracing/auth/security, then LiteLLM for cost and model routing

## Draft: Article 1 — The Journey

---

# From Ingestion and Ask to a Real Personal Agent

*How a simple retrieval tool became a personal system for learning, routing, tracing, and continuous improvement.*

---

[SCREENSHOT 1 PLACEHOLDER: PersGraph hero / landing page]

[SCREENSHOT 2 PLACEHOLDER: PersGraph website or dashboard showing a real action flow]

[SCREENSHOT 3 PLACEHOLDER: GitHub / repo / marketing HTML link section]

I didn't set out to build a personal AI agent.

I started with a very specific problem: I was saving articles, notes, and PDFs everywhere and never finding them when I needed them. The obvious tools — Notion, Obsidian, bookmarking apps — are useful, but they all rely on a kind of discipline I don't naturally keep up.

So I built something smaller and more direct.

PersGraph began with two commands:

- `/ingest <url>` — fetch a page, chunk it, embed it, store it
- `/ask <question>` — query everything I've saved and get a synthesized answer

That first version was intentionally modest. No dashboard. No orchestration layer. No agent loop. Just a Python-backed knowledge system and a Telegram bot for the interface.

That simplicity mattered because it gave me something I could actually use every day. And once I was using it every day, the system started teaching me what it needed next.

---

## Starting Small Was the First Best Practice

The temptation in AI system building is to reach for the full stack immediately: RAG, rerankers, agents, memory, tools, dashboards, background jobs, routing logic. I’ve done that. It usually produces something impressive-looking and hard to maintain.

PersGraph worked because it started with utility.

The ingestion/ask loop exposed the real shape of the problem:
- what gets saved
- how it gets chunked
- how it gets retrieved
- how to keep answers grounded
- how to make the system easy to operate

That led naturally into better engineering habits. Every useful addition came from friction I actually felt, not from architecture for its own sake.

---

## The System Grew by Applying Industry Learnings

As the tool matured, I kept turning day-to-day pain into system design.

Instead of throwing more features at it, I started layering in the kinds of practices I’d normally apply in a production system:

- tracing so I could see what the agent was doing
- secure auth behind a reverse proxy
- cleaner configuration boundaries
- public-repo secret hygiene
- recoverable scripts and repeatable commands
- documentation that matches the real system

That’s when PersGraph stopped being just a retrieval utility and started becoming a personal platform.

The progression was gradual:

1. **Ingest / ask** — the core loop
2. **Capture / task / place** — broader personal knowledge capture
3. **Tracing and observability** — understanding where time and money go
4. **Caddy + Flask hardening** — making the public site trustworthy
5. **Secrets and repo hygiene** — treating a public repo like one
6. **Workflow recovery** — restoring broken command surfaces instead of hand-waving them away

This wasn’t a rewrite. It was a series of upgrades that taught the system to behave more like a real service.

---

## Why LiteLLM Became the Next Step

Once the system was being used more often, two practical issues showed up:

- model costs started to matter
- different tasks clearly wanted different models

Some jobs needed a fast, low-cost model. Others needed stronger reasoning. A few were better handled by a model specialized for code or structure. Running everything through one path was convenient, but it wasn’t efficient.

That’s where LiteLLM came in.

LiteLLM let me introduce model routing without turning the whole project into a vendor-specific tangle. It became the layer that helped me manage:

- **cost control** — don’t spend premium tokens on trivial work
- **model circulation** — route tasks to the right model for the job
- **fallbacks** — keep the system working when one provider or model isn’t ideal
- **consistency** — keep the calling pattern stable even as the backend changes

That evolution felt very much in line with the rest of PersGraph: start small, observe what hurts, add the least complicated thing that solves the problem well.

---

## The Agent Began Helping Maintain Itself

The most convincing moment wasn’t a flashy feature. It was a debugging session.

I was fixing the public site at `persgraph.simplicore.ai` when the assistant helped trace a login loop, update session settings, fix Langfuse host config, scrub secrets from the repo, restore a broken command dispatcher, and update the docs to match the real setup.

That session was a proof point: the system wasn’t just storing and retrieving information anymore. It was participating in its own maintenance.

And the journey from ingest/ask to that point was exactly the point of the article.

---

## What the Journey Taught Me

The important lessons weren’t abstract AI lessons. They were operational lessons:

**1. Start with one useful loop.**
Ingest/ask was enough to create momentum.

**2. Add best practices as the system grows.**
Tracing, auth, secrets handling, and docs matter more than cleverness.

**3. Route work intentionally.**
LiteLLM made cost and model selection a first-class concern.

**4. Keep the public surface honest.**
The README, landing page, and live behavior should agree.

**5. Let the system evolve in response to real use.**
That’s where the best improvements came from.

---

## What Comes Next

PersGraph isn’t finished. It’s just more capable than it used to be.

The next layer is the scratchpad workflow — Scratchflow — for transient thinking and model handoffs. That deserves its own article.

For this one, the story is the progression itself:

from ingest/ask,
through best practices,
into observability, security, routing, and maintenance.

That’s how it became a real personal agent.

---

*If you’re building your own personal agent, don’t start with complexity. Start with a useful loop and let the system tell you what it needs next.*

---

## Why Starting Small Was the Right Move

The instinct when building AI tools is to reach for the full stack immediately: RAG + reranking + agents + memory + tools + dashboards. I've done that before. It always ends the same way — a complex system that's hard to debug, hard to explain, and abandoned after a few weeks.

PersGraph worked because it was useful on day one.

When I ingested my first article and asked a question about it, the answer was good. Good enough that I kept using it. And because I kept using it, I kept improving it.

That feedback loop — use it, notice what's missing, add it — is the real foundation. Not a grand plan.

---

## The Agent Grew From the Bottom Up

Over the following months, PersGraph grew naturally:

- `/note` and `/task` — quick capture via Telegram
- `/place` — a personal places graph (restaurants, cities, spots I want to remember)
- Morning briefing — a cron job that sends a daily digest at 8am
- Email ingestion — auto-classify incoming emails as tasks, notes, appointments, or URLs
- Travel planner — a dedicated trip planning page served via a Flask app
- Langfuse tracing — every command gets traced for latency and debugging
- Multi-user routing — family members get their own model tier and scoped search

None of these were planned upfront. Each one was a response to a real friction point.

---

## The Day the Agent Helped Fix Itself

The best evidence that PersGraph had become a real personal agent happened during a normal debugging session.

I was trying to fix a public login loop on `persgraph.simplicore.ai`. The site was protected by Caddy basic auth, but after entering credentials, the browser just kept showing the login page. Classic redirect loop.

What happened next wasn't just debugging. The agent:

1. Traced the issue from Caddy → Flask → session cookie settings
2. Identified that `SESSION_COOKIE_SECURE` wasn't set, so the browser was discarding the session
3. Patched `server.py` to fix the cookie config
4. Spotted that Langfuse was configured to export to `localhost:3000` — a server that didn't exist
5. Updated the Langfuse host to `us.cloud.langfuse.com` and validated the new credentials
6. Found hardcoded API keys in a tracked `.env` file in a **public repo**
7. Replaced them with safe placeholders
8. Added `.env` to `.gitignore` so it can never happen again
9. Updated the README and marketing page to match the real architecture
10. Committed everything with a clean, descriptive message

This was a 45-minute session. The agent did most of the inspection, patching, and verification.

That's not a chatbot. That's a maintenance partner.

---

## What PersGraph Taught Me About Building AI Systems

A few things I've learned that I don't see written about enough:

**1. Useful beats impressive.**
The best AI tools I've built are the ones I actually use every day. The ones I abandoned were impressive demos. Start with a real friction point, not a cool technique.

**2. Keep secrets out of tracked files. Always.**
If your repo is public, every file is public. `.env` should be in `.gitignore` from day one, not day 90. I learned this the hard way.

**3. Tracing is not optional.**
Without Langfuse, I had no idea which commands were slow, which were failing silently, or where the system was spending money. Tracing made PersGraph debuggable. Every command now gets traced automatically.

**4. Don't duplicate auth layers.**
Running Caddy basic auth in front of a Flask app that also has its own login creates a session management mess. Pick one. Caddy handles public auth; the app trusts the proxy.

**5. Recover from failure gracefully.**
`scripts/command.py` got corrupted to 2 lines. The system detected it, recovered it from git history, reconstructed it from spec, and validated it with a smoke test. That kind of resilience doesn't happen by accident — you have to build it in.

---

## What's Next

PersGraph is still growing. The next big thing is the Market Scout Agent — a background agent that monitors signals relevant to my work and surfaces them before I need to go looking.

But the most interesting development is something smaller: a transient scratchpad system for multi-model collaboration. More on that in a follow-up piece.

The short version: different AI models are better at different things. Claude/Sonnet is good at strategy and critique. GPT is good at drafting. Haiku is good at execution. A shared transient memory layer — one that doesn't pollute long-term memory — lets them hand off work cleanly.

That's the next article.

---

*If you're building your own personal agent, start smaller than you think. The system will tell you what it needs.*

---

## Log
- 2026-06-07: Scratchpad created. Full draft written from session context.
