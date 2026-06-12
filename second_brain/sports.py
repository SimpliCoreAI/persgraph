from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
API_BASE = "https://www.thesportsdb.com/api/v1/json/123"
SPORTS = ["soccer", "worldcup", "football", "nba"]
SPORT_LABELS = {"soccer": "Soccer", "worldcup": "World Cup", "football": "Football", "nba": "NBA"}
ALIASES = {"soccer": "worldcup"}

# Starter league set only. Expand later if needed.
LEAGUES = {
    "nba": [{"id": "4387", "name": "NBA"}],
    "football": [{"id": "4391", "name": "NFL"}],
    "worldcup": [
        {"id": "4429", "name": "FIFA World Cup"},
    ],
}


def _date_strings_window() -> list[str]:
    """Return UTC date strings to query for today's events.
    Since games may be scheduled early morning UTC (previous or next day UTC),
    which translates to today's PST, we query today's UTC and the next day's UTC.
    This captures games scheduled for early morning UTC tomorrow that are still
    on today's PST calendar (e.g., 2026-06-13 01:00 UTC = 2026-06-12 18:00 PST).
    """
    from datetime import timedelta
    now_utc = datetime.now(LOCAL_TZ).astimezone(ZoneInfo("UTC"))
    dates = [
        now_utc.strftime("%Y-%m-%d"),
        (now_utc + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]
    return dates


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
    today_local = datetime.now(LOCAL_TZ).date()
    for d in _date_strings_window():
        date_q = urllib.parse.quote(d)
        url = f"{API_BASE}/eventsday.php?d={date_q}&l={league_id}"
        data = _fetch_json(url)
        for e in (data.get("events") or []):
            dt = _parse_event_dt(e.get("dateEvent") or e.get("dateEventLocal"), e.get("strTime") or e.get("strTimeLocal"))
            if dt and dt.date() != today_local:
                continue
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
        "venue": e.get("strVenue") or "",
        "round": e.get("intRound") or "",
    }


def _status_text(status: str) -> str:
    s = (status or '').upper()
    if s == 'NS':
        return 'Scheduled'
    if s == 'FT':
        return 'Final'
    return status or 'Scheduled'


def _format_events(events: list[dict], sport_filter: str) -> str:
    target = ALIASES.get(sport_filter, sport_filter)
    if not events:
        label = "sports" if target == "all" else SPORT_LABELS.get(target, target)
        return f"🏟 No {label.lower()} games found for today / near-now."

    events.sort(key=lambda x: (x["dt"] is None, x["dt"] or datetime.max.replace(tzinfo=LOCAL_TZ), x["league"], x["home"]))
    lines = []
    if target == 'worldcup':
        lines.append("🏆 World Cup — today (PST)")
    else:
        lines.append("🏟 Today's sports schedule" if target == "all" else f"🏟 {SPORT_LABELS.get(target, target.title())} schedule")
    lines.append("")
    for e in events[:20]:
        when = e["dt"].strftime("%-I:%M %p PST") if e["dt"] else "Time TBD"
        matchup = f"{e['home']} vs {e['away']}" if e['away'] != 'TBD' else e['home']
        lines.append(f"⚽ {matchup}")
        meta = [when]
        if e.get('venue'):
            meta.append(e['venue'])
        if target == 'worldcup' and e.get('round'):
            meta.append(f"Group stage · Matchday {e['round']}")
        status = _status_text(e.get('status', ''))
        if status and status != 'Scheduled':
            meta.append(status)
        lines.append(f"   {' · '.join(meta)}")
    return "\n".join(lines)


def get_sports_status(query: str) -> str:
    raw = (query or '').strip().lower()
    sport = raw or 'all'
    sport = ALIASES.get(sport, sport)
    if sport not in SPORTS and sport != 'all':
        return '❌ Usage: /sport [soccer|worldcup|football|nba]'

    selected = [s for s in SPORTS if s != 'soccer'] if sport == 'all' else [sport]
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
