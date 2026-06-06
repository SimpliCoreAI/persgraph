# travel/AGENTS.md — Travel Planner Conventions

## What Lives Here
- `index.html` — standalone travel planner UI (served on port 8766)
- Login: jolly / persgraph2026
- Public URL: http://5.78.196.42:8766

## Data Schema
- Trip data: stored in Persgraph SQLite (places collection) + config.yaml trip entries
- Weather: fetched via wttr.in (`curl "wttr.in/<city>?format=3"`)
- Daily briefings: isolated cron job per trip, 7am local time, Haiku model

## Trip Briefing Pattern
- Set up ~1 week before trip departure
- Cron schedule: 14:00 UTC = 7am PDT | adjust for local timezone
- Payload: weather + day plan, wttr.in format, Haiku model
- After trip: disable cron, log cron id to MEMORY.md

## Active Trips
- Japan: cron id `68839e9e` (22:00 UTC, Jun 22–Jul 1)
- Tahoe Jul 3–5: set up ~Jun 27
- Riverside Jul 11–13: set up ~Jul 7

## Adding New Trips
1. Create trip entry with dates, cities, daily plan
2. Register cron job ~1 week before (14:00 UTC for 7am PDT)
3. Log cron id in MEMORY.md under PersGraph > Trip daily briefing pattern
4. Disable + remove cron after trip ends

## UI Conventions (index.html)
- Self-contained HTML — no build step, no npm
- Vanilla JS only — no frameworks
- Served directly by Python http.server or embedded webserver
