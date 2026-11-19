"""Bring a season file up to date from ESPN: results, scoring events, lineups
with substitution minutes, and (optionally) matches the file lacks.

Used by ``rugby data enrich-events`` to fill historical gaps and by
``rugby data update`` for the club competitions, whose original feed now needs
an app id we don't have. What it never does:

* replace scoring events a match already has, or a lineup that already
  records substitution minutes;
* write scoring events that don't add up to the final score (ESPN has a few
  matches with a kick missing); the result is still recorded;
* move a match between files or change its teams.

Matches it adds or fills are tagged ``"events_source": "espn"`` (and
``"lineup_source": "espn"`` when the lineup came from ESPN), so they can be
told apart from the original feed. ESPN has no missed kicks.
"""

import collections
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .scrapers import espn
from .scrapers.espn import ESPN_LEAGUES, REQUEST_PAUSE, find_event, has_minutes, same_team
from .team_names import canonical_team_name

COVID_RESTART_END = '2020-09-20'   # 2019-20 restarted in Aug 2020 and ended 12 Sep 2020


def season_window(season: str, calendar_year: bool) -> Tuple[str, str]:
    """First and last dates (inclusive) of a season's matches."""
    start = int(season.split('-')[0])
    if calendar_year:
        return f'{start}-01-01', f'{start}-12-31'
    lo, hi = f'{start}-08-01', f'{start + 1}-07-31'
    if start == 2019:
        hi = COVID_RESTART_END
    elif start == 2020:
        lo = (_day(COVID_RESTART_END) + timedelta(days=1)).strftime('%Y-%m-%d')
    return lo, hi


def load_matches(path: Path) -> Optional[List[dict]]:
    """A season file as a list of matches, whatever format it is stored in."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and 'home' in data and 'matches' not in data:   # legacy column-oriented
        data = [{c: data[c][k] for c in data} for k in data['home']]
    return data if isinstance(data, list) else None


def save_matches(path: Path, matches: List[dict]) -> None:
    matches.sort(key=lambda m: str(m.get('date') or ''))
    Path(path).write_text(json.dumps(matches, indent=2))


def _has_result(m: dict) -> bool:
    return (m.get('home') or {}).get('score') is not None and (m.get('away') or {}).get('score') is not None


def _has_events(m: dict) -> bool:
    return bool((m.get('home') or {}).get('scores') or (m.get('away') or {}).get('scores'))


def _is_placeholder(m: dict) -> bool:
    return {(m.get('home') or {}).get('team'), (m.get('away') or {}).get('team')} <= {'TBC', 'TBD', None, ''}


def resolve_team(espn_name: str, known: List[str]) -> str:
    """The spelling this file already uses for an ESPN team, else canonical."""
    hits = [k for k in known if same_team(k, espn_name)]
    if len(hits) == 1:
        return hits[0]
    return canonical_team_name(espn_name) or espn_name


def _day(s: str) -> datetime:
    return datetime.strptime(str(s)[:10], '%Y-%m-%d')


def _round_from_neighbours(date: str, matches: List[dict]) -> Dict:
    """Round fields for a new match: those of the fixtures within three days,
    if the file records rounds at all."""
    if not any('round' in m for m in matches):
        return {}
    day = _day(date)
    near = [m for m in matches if m.get('round') is not None and str(m.get('date', ''))[:4].isdigit()
            and abs((_day(m['date']) - day).days) <= 3]
    if not near:
        return {'round': None, 'round_type': None}
    rnd, _ = collections.Counter((m.get('round'), m.get('round_type')) for m in near).most_common(1)[0]
    return {'round': rnd[0], 'round_type': rnd[1]}


def _same_fixture(m: dict, e: dict) -> bool:
    """Our match and an ESPN event are the same fixture: same two teams (either
    way round: a few of our files have home and away swapped) and dates within
    a day. Scores are not compared."""
    if not str(m.get('date', ''))[:4].isdigit() or abs((_day(m['date']) - _day(e['date'])).days) > 1:
        return False
    h, a = (m.get('home') or {}).get('team', ''), (m.get('away') or {}).get('team', '')
    return ((same_team(h, e['home']) and same_team(a, e['away']))
            or (same_team(h, e['away']) and same_team(a, e['home'])))


def _apply_detail(m: dict, detail: Dict[str, dict], stats: collections.Counter) -> bool:
    """Copy scoring events and lineups from ``detail`` into ``m`` where they
    are missing or improve on what's there. Returns True if anything changed."""
    changed = lineup_changed = False
    if not _has_events(m):
        if all(espn.scores_reconcile(detail[s]['scores'], m[s].get('score')) for s in ('home', 'away')):
            for s in ('home', 'away'):
                m[s]['scores'] = detail[s]['scores']
            m['events_source'] = 'espn'
            stats['events_added'] += 1
            changed = True
        else:
            stats['events_dont_add_up'] += 1
    for s in ('home', 'away'):
        ours, theirs = m[s].get('lineup'), detail[s]['lineup']
        if has_minutes(ours) or not has_minutes(theirs) and ours and len(ours) >= len(theirs):
            continue
        m[s]['lineup'] = theirs
        m['lineup_source'] = 'espn'
        changed = lineup_changed = True
    stats['lineups_added'] += lineup_changed
    return changed


def _detail(slug: int, event: dict, match: dict) -> Optional[Dict[str, dict]]:
    summary = espn.fetch_summary(slug, event['id'])
    time.sleep(REQUEST_PAUSE)
    plays = espn.fetch_plays(slug, event['id'])
    time.sleep(REQUEST_PAUSE)
    existing = {s: (match.get(s) or {}).get('lineup') for s in ('home', 'away')}
    return espn.timeline_detail(summary, plays, match.get('date', event['date']), existing)


def sync_season(prefix: str, season: str, json_dir: Path, dry_run: bool = False,
                add_missing: bool = False, fixtures: bool = False,
                events_cache: Optional[Dict] = None) -> Dict:
    """Fill one season file from ESPN. Returns counts of what happened.

    ``add_missing`` adds completed ESPN matches the file lacks; ``fixtures``
    also adds and re-dates unplayed ones (the weekly update uses both).
    """
    cfg = ESPN_LEAGUES[prefix]
    slug = cfg['slug']
    path = Path(json_dir) / f'{prefix}-{season}.json'
    stats: collections.Counter = collections.Counter()
    matches = load_matches(path)
    if matches is None:
        if not (add_missing or fixtures):
            return {'no_file': 1}
        matches = []

    lo, hi = season_window(season, cfg['calendar_year'])
    events: List[dict] = []
    for y in range(int(lo[:4]), int(hi[:4]) + 1):
        key = (slug, y, 'all')
        if events_cache is None or key not in events_cache:
            got = espn.fetch_events(slug, y, include_unplayed=True)
            time.sleep(REQUEST_PAUSE)
            if events_cache is not None:
                events_cache[key] = got
        else:
            got = events_cache[key]
        events += [e for e in got if lo <= e['date'] <= hi]
    # ESPN marks a few never-played matches completed at 0-0
    events = [e for e in events if not (e['completed'] and e['home_score'] == 0 and e['away_score'] == 0)]
    if not events:
        stats['no_espn_events'] += 1
        return dict(stats)
    played = [e for e in events if e['completed']]
    changed = False
    paired = set()

    # 1. matches we have: results, events and lineups
    for m in matches:
        if _is_placeholder(m) or m.get('status') == 'void':
            continue
        had_result = _has_result(m)
        if had_result:
            event, why = find_event(m, played)
        else:   # fixture: pair on date and teams only
            event, why = find_event({**m, 'home': {**m['home'], 'score': None}}, played)
        if event is None:
            if had_result and not _has_events(m):
                stats['skip_' + why] += 1
            continue
        paired.add(event['id'])
        if not had_result:
            if event['home_score'] is None or event['away_score'] is None:
                continue
            m['home']['score'], m['away']['score'] = event['home_score'], event['away_score']
            stats['results_added'] += 1
            changed = True
        if _has_events(m) and has_minutes(m['home'].get('lineup')) and has_minutes(m['away'].get('lineup')):
            continue
        detail = _detail(slug, event, m)
        if detail is None:
            stats['skip_no_roster'] += 1
            continue
        changed |= _apply_detail(m, detail, stats)

    # 2. ESPN matches we don't have
    if add_missing or fixtures:
        known = sorted({m[s]['team'] for m in matches for s in ('home', 'away')
                        if (m.get(s) or {}).get('team') and not _is_placeholder(m)})
        for e in events:
            if e['id'] in paired or (not e['completed'] and not fixtures):
                continue
            home, away = resolve_team(e['home'], known), resolve_team(e['away'], known)
            same = [m for m in matches if _same_fixture(m, e)]
            if same:
                m = same[0]
                if e['completed']:
                    stats['already_here_differs'] += 1      # ESPN's score or orientation differs
                elif fixtures and not _has_result(m) and str(m['date'])[:16] != e['kickoff'][:16] \
                        and same_team(m['home']['team'], e['home']):
                    m['date'] = e['kickoff']                # kick-off time moved
                    stats['redated'] += 1
                    changed = True
                continue
            # an unplayed fixture of ours with these teams, moved by more than a day
            moved = [m for m in matches if not _has_result(m) and not _is_placeholder(m)
                     and same_team(m['home']['team'], e['home']) and same_team(m['away']['team'], e['away'])
                     and abs((_day(m['date']) - _day(e['date'])).days) <= 60]
            if len(moved) == 1:
                target = moved[0]
                target['date'] = e['kickoff']
                stats['redated'] += 1
            else:
                placeholder = [m for m in matches if _is_placeholder(m) and str(m.get('date', ''))[:4].isdigit()
                               and abs((_day(m['date']) - _day(e['date'])).days) <= 1]
                target = {'home': {'team': home, 'score': None, 'scores': [], 'lineup': {}},
                          'away': {'team': away, 'score': None, 'scores': [], 'lineup': {}},
                          'date': e['kickoff'], 'stadium': e.get('venue'), 'attendance': e.get('attendance') or None}
                if placeholder:     # a knockout slot: take its round and drop it
                    p = placeholder[0]
                    target.update({k: p[k] for k in ('round', 'round_type') if k in p})
                    matches.remove(p)
                    stats['placeholders_filled'] += 1
                else:
                    target.update(_round_from_neighbours(e['kickoff'], matches))
                target['source'] = 'espn'
                matches.append(target)
                stats['matches_added' if e['completed'] else 'fixtures_added'] += 1
            changed = True
            if e['completed'] and e['home_score'] is not None:
                target['home']['score'], target['away']['score'] = e['home_score'], e['away_score']
                detail = _detail(slug, e, target)
                if detail is not None:
                    _apply_detail(target, detail, stats)

    if changed and not dry_run:
        save_matches(path, matches)
    return dict(stats)
