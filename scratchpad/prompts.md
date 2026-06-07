# Scratchpad Invocation Prompts

## 1) Start a scratchpad topic
Use when you want a temporary working memory for a topic.

Prompt:
> Start a scratchpad for: <topic>. Keep it transient, model-agnostic, and separate from MEMORY.md. Capture goal, context, decisions, open questions, next actions, and handoff notes. Do not promote anything to long-term memory.

## 2) Update a scratchpad topic
Use when more context arrives.

Prompt:
> Update the scratchpad for <topic> with this new context: <paste>. Keep the scratchpad concise. Preserve decisions, add open questions, and update next actions. Do not write to MEMORY.md.

## 3) Handoff to another model
Use when one model should continue the work.

Prompt:
> Handoff the scratchpad for <topic> to <model>. Summarize current context, decisions, and the exact next actions. Keep it short and actionable. Do not rewrite history.

Examples:
- `to GPT`: draft the article, propose wording, summarize options
- `to Claude/Sonnet`: evaluate structure, advise on strategy, identify risks
- `to Haiku`: execute the concrete edits or checks

## 4) Close a scratchpad topic
Use when the work is done.

Prompt:
> Close the scratchpad for <topic>. Summarize final outcome, decisions, and any durable lessons. Mark the scratchpad as closed and do not keep raw working notes unless explicitly requested.

## 5) Archive or prune
Use when you want to clean up old work.

Prompt:
> Review scratchpad topics older than <date> and archive or delete anything closed. Keep only active work visible.

## 6) Use it as the transient memory layer
Use when you want the agent to maintain working state across models without touching MEMORY.md.

Prompt:
> Use the scratchpad as transient memory for this task. Treat MEMORY.md as off-limits unless something becomes durable and worth curating. Keep the scratchpad concise and update it as the source of truth for this topic.
