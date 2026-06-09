from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
API_BASE = "https://www.thesportsdb.com/api/v1/json/123"
SPORTS = ["soccer", "football", "nba"]
SPORT_LABELS = {"soccer": "Soccer", "football": "Football", "nba": "NBA"}

# Starter league set only. Expand later if needed.
LEAGUES = {
    "nba": [{"id": "4387", "name": "NBA"}],
    "football": [{"id": "4391", "name": "NFL"}],
    "soccer": [
        {"id": "4328", "name": "English Premier League"},
        {"id": "4480", "name": "UEFA Champions League"},
        {"id": "4346", "name": "MLS"},
    ],
}


def _date_strings_window() -> list[str]:
    now = datetime.now(LOCAL_TZ)
    return [
        now.strftime("%Y-%m-%d"),
        (now.replace(hour=0, minute=0, second=0, microsecond=0)).strftime("%Y-%m-%d"),
        __import__('datetime').datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d"),
        (now + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d"),
    ]


def _parse_event_dt(date_str: str | None, time_str: str | None) -> datetime | None:
    if not date_str:
        return None
    raw_time = (time_str or "00:00:00").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(f"{date_str} {raw_time}" if fmt != "%Y-%m-%d" else date_str, fmt)
            return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)
        except ValueError:
            continue
    return None


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "PersGraph/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _events_for_league_today(league_id: str) -> list[dict]:
    seen = set()
    out = []
    for d in _date_strings_window():
        date_q = urllib.parse.quote(d)
        url = f"{API_BASE}/eventsday.php?d={date_q}&l={league_id}"
        data = _fetch_json(url)
        for e in (data.get("events") or []):
            eid = e.get("idEvent")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            out.append(e)
    return out


def _normalize_event(sport: str, league_name: str, e: dict) -> dict | None:
    dt = _parse_event_dt(e.get("dateEvent") or e.get("dateEventLocal"), e.get("strTime") or e.get("strTimeLocal"))
    home = e.get("strHomeTeam") or e.get("strEvent") or "Unknown"
    away = e.get("strAwayTeam") or "TBD"
    status = (e.get("strStatus") or "Scheduled").strip()
    return {
        "sport": sport,
        "league": league_name,
        "home": home,
        "away": away,
        "status": status,
        "dt": dt,
    }


def _format_events(events: list[dict], sport_filter: str) -> str:
    if not events:
        target = "sports" if sport_filter == "all" else sport_filter
        return f"🏟 No {target} games found for today / near-now."

    events.sort(key=lambda x: (x["dt"] is None, x["dt"] or datetime.max.replace(tzinfo=LOCAL_TZ), x["league"], x["home"]))
    lines = []
    header = "🏟 Today's sports schedule" if sport_filter == "all" else f"🏟 {SPORT_LABELS.get(sport_filter, sport_filter.title())} schedule"
    lines.append(header)
    lines.append("")
    for e in events[:20]:
        when = e["dt"].strftime("%b %d, %-I:%M %p %Z") if e["dt"] else "Time TBD"
        matchup = f"{e['home']} vs {e['away']}" if e['away'] != 'TBD' else e['home']
        prefix = SPORT_LABELS.get(e["sport"], e["sport"].title())
        lines.append(f"• {prefix} — {matchup} — {when}")
    return "\n".join(lines)


def get_sports_status(query: str) -> str:
    raw = (query or '').strip().lower()
    sport = raw or 'all'
    if sport not in SPORTS and sport != 'all':
        return '❌ Usage: /sport [soccer|football|nba]'

    selected = SPORTS if sport == 'all' else [sport]
    all_events: list[dict] = []
    errors: list[str] = []

    for s in selected:
        for league in LEAGUES.get(s, []):
            try:
                events = _events_for_league_today(league['id'])
                for e in events:
                    norm = _normalize_event(s, league['name'], e)
                    if norm:
                        all_events.append(norm)
            except Exception as ex:
                errors.append(f"{league['name']}")

    if not all_events and errors:
        return f"⚠️ Sports schedule lookup failed for today. Tried: {', '.join(errors[:5])}"

    return _format_events(all_events, sport)
