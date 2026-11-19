"""Lineups, scoring events and results from ESPN's public rugby JSON.

Two endpoints are used: the *site* API (scoreboard, and a match summary with
rosters) and the *core* API's play-by-play, which has every score, card and
substitution with its minute and the player's ESPN id. The play-by-play is
what ``timeline_detail`` turns into our ``scores`` and minute-stamped lineups;
it has no missed kicks. The rest of this note is about rosters alone.

ESPN gives who was in the matchday 23 (jersey, name) but *not* when anyone
came on or off, so lineups built here carry no substitution minutes:
starters are ``on: [0]``, the bench ``on: []``, ``off`` empty. Matches enriched
from here are tagged ``"lineup_source": "espn"`` so consumers can tell.

Coverage was measured before wiring anything up (6 matches sampled per season):
Top 14 2010-2026, Super Rugby Pacific 2022-2026 and the NPC 2016-2026 mostly
have rosters. The Currie Cup has none, and Super Rugby before 2022 isn't under
this feed, so neither is configured here.

ESPN's ``starter`` flag is unreliable (false for every player in Super Rugby
and the NPC), so starters are taken from the jersey number: 1-15 start.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

from ..team_names import canonical_team_name

BASE = "https://site.api.espn.com/apis/site/v2/sports/rugby"
CORE = "https://sports.core.api.espn.com/v2/sports/rugby/leagues"
HEADERS = {'User-Agent': 'RugbyDataBot/1.0 (https://github.com/transientlunatic/Rugby-Data; mail@daniel-williams.co.uk)'}
REQUEST_PAUSE = 0.25   # seconds between requests: be polite to a public endpoint

# our competition -> ESPN league slug, and whether a season lies in one calendar year
ESPN_LEAGUES: Dict[str, Dict] = {
    'celtic': {'slug': 270557, 'calendar_year': False},
    'premiership': {'slug': 267979, 'calendar_year': False},
    'euro-champions': {'slug': 271937, 'calendar_year': False},
    'euro-challenge': {'slug': 272073, 'calendar_year': False},
    'top14': {'slug': 270559, 'calendar_year': False},
    'super-rugby': {'slug': 242041, 'calendar_year': True},
    'npc': {'slug': 270563, 'calendar_year': True},
}


def _get(url: str, **params) -> Optional[dict]:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        except requests.RequestException:
            time.sleep(3)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        return None
    return None


def fetch_events(slug: int, year: int, include_unplayed: bool = False) -> List[dict]:
    """Matches ESPN lists for a calendar year, normalised. Completed only,
    unless ``include_unplayed`` (postponed and cancelled ones are never kept)."""
    data = _get(f"{BASE}/{slug}/scoreboard", dates=str(year), limit=500) or {}
    events = []
    for e in data.get('events', []):
        status = e.get('status', {}).get('type', {})
        completed = bool(status.get('completed'))
        if not completed and (not include_unplayed or status.get('state') != 'pre'
                              or status.get('name') in ('STATUS_POSTPONED', 'STATUS_CANCELED')):
            continue
        comp = e['competitions'][0]
        sides = {c['homeAway']: c for c in comp['competitors']}
        if 'home' not in sides or 'away' not in sides:
            continue

        def score(c):
            try:
                return int(c.get('score')) if completed else None
            except (TypeError, ValueError):
                return None
        events.append({
            'id': e['id'],
            'date': e['date'][:10],
            'home': sides['home']['team']['displayName'],
            'away': sides['away']['team']['displayName'],
            'home_score': score(sides['home']),
            'away_score': score(sides['away']),
            'completed': completed,
            'kickoff': _iso(e['date']),
            'venue': (comp.get('venue') or {}).get('fullName'),
            'attendance': comp.get('attendance'),
        })
    return events


def _iso(espn_date: str) -> str:
    """"2026-10-31T19:45Z" -> "2026-10-31T19:45:00.000Z" (the main feed's form)."""
    try:
        return datetime.strptime(espn_date, '%Y-%m-%dT%H:%MZ').strftime('%Y-%m-%dT%H:%M:%S.000Z')
    except ValueError:
        return espn_date


def lineup_from_roster(roster: List[dict]) -> Dict[str, dict]:
    """ESPN roster -> our lineup shape, keyed by jersey number."""
    lineup: Dict[str, dict] = {}
    for p in roster:
        try:
            jersey = int(p.get('jersey'))
        except (TypeError, ValueError):
            continue
        name = (p.get('athlete') or {}).get('displayName')
        if not name or str(jersey) in lineup:
            continue
        lineup[str(jersey)] = {
            'name': name,
            'on': [0] if jersey <= 15 else [],
            'off': [], 'reds': [], 'yellows': [],
        }
    return lineup


def fetch_lineups(slug: int, event_id: str) -> Optional[Dict[str, Dict[str, dict]]]:
    """{'home': lineup, 'away': lineup} for one match, or None if ESPN has no
    full roster (15 starters and at least one replacement, both sides)."""
    data = _get(f"{BASE}/{slug}/summary", event=event_id) or {}
    out = {}
    for r in data.get('rosters') or []:
        side = r.get('homeAway')
        if side in ('home', 'away'):
            out[side] = lineup_from_roster(r.get('roster') or [])
    if set(out) != {'home', 'away'}:
        return None
    for lineup in out.values():
        starters = sum(1 for j in lineup if int(j) <= 15)
        if starters < 15 or len(lineup) <= 15:
            return None
    return out


# -- matching ESPN events to our matches ---------------------------------------

# ESPN spellings that aren't a prefix/suffix of ours (compared after _norm)
ESPN_ALIASES = {
    'stade toulousain': 'toulouse',
    'nsw waratahs': 'new south wales waratahs',
    'benetton treviso': 'benetton rugby',
}


def _clean(name: str) -> str:
    name = re.sub(r'[^a-z0-9 ]', '', (name or '').lower().replace('-', ' ')).strip()
    return ESPN_ALIASES.get(name, name)


def _norm(name: str) -> str:
    return _clean(canonical_team_name(name) or '')


def _names_agree(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a == b or a.startswith(b + ' ') or b.startswith(a + ' ') or a.endswith(' ' + b) or b.endswith(' ' + a)


def same_team(ours: str, theirs: str) -> bool:
    """Equal after canonicalising, or one name is the other's last words
    ("Reds" / "Queensland Reds", "Auckland" / "Auckland Mitre 10 Cup").
    Raw spellings are compared too, because canonicalising can point a short
    name at an old sponsor's ("Lions" -> "Emirates Lions" when the file says
    "Fidelity SecureDrive Lions")."""
    return _names_agree(_norm(ours), _norm(theirs)) or _names_agree(_clean(ours), _clean(theirs))


def find_event(match: dict, events: List[dict]) -> Tuple[Optional[dict], str]:
    """The ESPN event for one of our matches, and why not if there isn't one.

    Same orientation, a date within a day, and (where both sides have scores)
    the same scores, which guards against pairing the wrong fixture.
    """
    try:
        day = datetime.strptime(str(match['date'])[:10], '%Y-%m-%d')
    except (KeyError, ValueError):
        return None, 'bad_date'
    window = {(day + timedelta(days=d)).strftime('%Y-%m-%d') for d in (-1, 0, 1)}
    home, away = match['home'], match['away']
    candidates = [e for e in events if e['date'] in window
                  and same_team(home.get('team', ''), e['home']) and same_team(away.get('team', ''), e['away'])]
    if not candidates:
        swapped = [e for e in events if e['date'] in window
                   and same_team(home.get('team', ''), e['away']) and same_team(away.get('team', ''), e['home'])]
        return None, 'swapped_orientation' if swapped else 'no_event'
    hs, as_ = home.get('score'), away.get('score')
    if hs is not None and as_ is not None:
        candidates = [e for e in candidates if (e['home_score'], e['away_score']) in ((hs, as_), (None, None))]
    if len(candidates) != 1:
        return None, 'score_mismatch' if not candidates else 'ambiguous'
    return candidates[0], 'ok'


# -- deciding whether ESPN's lineup is better ----------------------------------

def has_minutes(lineup: Optional[dict]) -> bool:
    """True if the lineup records when players came on/off or were carded."""
    for p in (lineup or {}).values():
        if p.get('off') or p.get('reds') or p.get('yellows') or len(p.get('on') or []) > 1:
            return True
        if p.get('on') and p['on'][0] > 0:      # came on later than kick-off
            return True
    return False


def is_better(existing: Optional[dict], new: dict) -> bool:
    """Replace only when it improves things. A lineup with substitution minutes
    is never replaced (ESPN has none); a missing or shorter one is."""
    if not existing:
        return True
    if has_minutes(existing):
        return False
    return len(new) > len(existing)


# -- play-by-play: scoring events and minute-stamped lineups -------------------

# ESPN play type -> (our type, points). Spelling follows the main feed.
SCORING_PLAYS = {
    'try': ('Try', 5),
    'conversion': ('Conversion', 2),
    'penalty goal': ('Penalty', 3),
    'drop goal': ('Drop goal', 3),
    'penalty try': ('Penalty Try', None),    # 5 before July 2017 (plus a kick), 7 after
}
PENALTY_TRY_SEVEN_FROM = '2017-07-01'


def fetch_plays(slug: int, event_id: str) -> List[dict]:
    """The core API's play-by-play for one match (empty if ESPN has none)."""
    data = _get(f"{CORE}/{slug}/events/{event_id}/competitions/{event_id}/plays", limit=500) or {}
    return data.get('items') or []


def fetch_summary(slug: int, event_id: str) -> dict:
    return _get(f"{BASE}/{slug}/summary", event=event_id) or {}


def minute_of(clock: Optional[dict]) -> int:
    """ESPN clock -> match minute. "23'" is 23; stoppage time "80'+2" is 82."""
    clock = clock or {}
    hit = re.match(r"\s*(\d+)'?\s*(?:\+\s*(\d+))?", str(clock.get('displayValue') or ''))
    if hit:
        return int(hit.group(1)) + int(hit.group(2) or 0)
    try:
        return int(-(-float(clock.get('value', 0)) // 60))
    except (TypeError, ValueError):
        return 0


def _ref_id(ref: Optional[str], kind: str) -> Optional[str]:
    hit = re.search(rf'/{kind}/(\d+)', ref or '')
    return hit.group(1) if hit else None


def _surname(name: str) -> str:
    parts = re.sub(r'[^a-z ]', '', (name or '').lower().replace('-', ' ')).split()
    return parts[-1] if parts else ''


def timeline_detail(summary: dict, plays: List[dict], match_date: str,
                    existing: Optional[Dict[str, dict]] = None) -> Optional[Dict[str, dict]]:
    """Build ``{'home': {'lineup', 'scores', 'team_id'}, 'away': ...}`` from a
    summary's rosters and the play-by-play, or None without rosters.

    Lineups are keyed by jersey, with ``on``/``off``/card minutes from the
    play-by-play. Scorers are named as in ``existing`` lineups when the same
    jersey has the same surname there (so a match keeps one spelling per
    player), otherwise as ESPN names them.
    """
    sides: Dict[str, dict] = {}
    by_athlete: Dict[str, Tuple[str, str]] = {}
    team_side: Dict[str, str] = {}
    for r in summary.get('rosters') or []:
        side = r.get('homeAway')
        if side not in ('home', 'away'):
            continue
        team_side[str((r.get('team') or {}).get('id'))] = side
        lineup = lineup_from_roster(r.get('roster') or [])
        for p in r.get('roster') or []:
            aid = str((p.get('athlete') or {}).get('id') or '')
            if aid and str(p.get('jersey')).isdigit() and str(int(p['jersey'])) in lineup:
                by_athlete[aid] = (side, str(int(p['jersey'])))
        sides[side] = {'lineup': lineup, 'scores': [], 'team_id': (r.get('team') or {}).get('id')}
    if set(sides) != {'home', 'away'}:
        return None

    def name_for(side: str, jersey: str) -> str:
        espn_name = sides[side]['lineup'][jersey]['name']
        ours = ((existing or {}).get(side) or {}).get(jersey, {}).get('name')
        return ours if ours and _surname(ours) == _surname(espn_name) else espn_name

    def ordered(p):
        return (int((p.get('period') or {}).get('number') or 0), float((p.get('clock') or {}).get('value') or 0))

    for p in sorted(plays, key=ordered):
        kind = (p.get('type') or {}).get('text', '').lower()
        minute = minute_of(p.get('clock'))
        aid = next((_ref_id((x.get('athlete') or {}).get('$ref'), 'athletes')
                    for x in p.get('participants') or [] if x.get('athlete')), None)
        side, jersey = by_athlete.get(aid, (None, None))
        if side is None:
            side = team_side.get(_ref_id((p.get('team') or {}).get('$ref'), 'teams'))
        if side is None:
            continue
        if kind in SCORING_PLAYS:
            our_type, value = SCORING_PLAYS[kind]
            if value is None:
                value = 7 if str(match_date)[:10] >= PENALTY_TRY_SEVEN_FROM else 5
            sides[side]['scores'].append({'minute': minute, 'type': our_type,
                                          'player': name_for(side, jersey) if jersey else None,
                                          'value': value})
        elif jersey is None:
            continue
        elif kind == 'substitute on':
            if minute not in sides[side]['lineup'][jersey]['on']:
                sides[side]['lineup'][jersey]['on'].append(minute)
        elif kind == 'player substituted':
            sides[side]['lineup'][jersey]['off'].append(minute)
        elif kind == 'yellow card':
            sides[side]['lineup'][jersey]['yellows'].append(minute)
        elif kind == 'red card':
            sides[side]['lineup'][jersey]['reds'].append(minute)
    return sides


def scores_reconcile(scores: List[dict], final: Optional[int]) -> bool:
    return final is not None and sum(s.get('value') or 0 for s in scores) == final
