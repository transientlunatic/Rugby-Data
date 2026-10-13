"""Lineups from ESPN's public rugby JSON, for competitions the main feed lacks.

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
HEADERS = {'User-Agent': 'RugbyDataBot/1.0 (https://github.com/transientlunatic/Rugby-Data; mail@daniel-williams.co.uk)'}
REQUEST_PAUSE = 0.25   # seconds between requests: be polite to a public endpoint

# our competition -> ESPN league slug, and whether a season lies in one calendar year
ESPN_LEAGUES: Dict[str, Dict] = {
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


def fetch_events(slug: int, year: int) -> List[dict]:
    """Completed matches ESPN lists for a calendar year, normalised."""
    data = _get(f"{BASE}/{slug}/scoreboard", dates=str(year), limit=400) or {}
    events = []
    for e in data.get('events', []):
        if not e.get('status', {}).get('type', {}).get('completed'):
            continue
        sides = {c['homeAway']: c for c in e['competitions'][0]['competitors']}
        if 'home' not in sides or 'away' not in sides:
            continue

        def score(c):
            try:
                return int(c.get('score'))
            except (TypeError, ValueError):
                return None
        events.append({
            'id': e['id'],
            'date': e['date'][:10],
            'home': sides['home']['team']['displayName'],
            'away': sides['away']['team']['displayName'],
            'home_score': score(sides['home']),
            'away_score': score(sides['away']),
        })
    return events


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
}


def _norm(name: str) -> str:
    name = canonical_team_name(name) or ''
    name = re.sub(r'[^a-z0-9 ]', '', name.lower().replace('-', ' ')).strip()
    return ESPN_ALIASES.get(name, name)


def same_team(ours: str, theirs: str) -> bool:
    """Equal after canonicalising, or one name is the other's last words
    ("Reds" / "Queensland Reds", "Auckland" / "Auckland Mitre 10 Cup")."""
    a, b = _norm(ours), _norm(theirs)
    if not a or not b:
        return False
    if a == b:
        return True
    return a.startswith(b + ' ') or b.startswith(a + ' ') or a.endswith(' ' + b) or b.endswith(' ' + a)


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
