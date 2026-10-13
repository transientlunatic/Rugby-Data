"""Repair match dates that are in the wrong year.

Two historical faults, found while matching lineups to ESPN:

* ``shift_late_autumn``: in some northern-hemisphere files (Celtic and Top 14
  2017-19) the August-December matches carry the *following* year. A season
  starting in year Y never holds August-December dates in Y+1, so those are
  moved back a year. Checked against ESPN's own dates: every match it could
  pair (Top 14 186, Celtic 136) agreed with the corrected date.
* ``repair_from_espn``: the Top 14 files for 2010-16 have every date set to
  2019 (and two are labelled a year early). Only the year is wrong; it is
  rebuilt from the season, which ESPN identifies and cross-checks.
"""

import collections
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .scrapers.espn import ESPN_LEAGUES, REQUEST_PAUSE, fetch_events, same_team

NORTHERN = {'celtic', 'premiership', 'top14', 'pro-d2', 'championship', 'euro-champions', 'euro-challenge'}
COVID_SEASON = 2019   # 2019-20 ran on into autumn 2020


def season_of(name: str) -> Optional[Tuple[str, int, int]]:
    m = re.match(r'(.+?)-(\d{4})-(\d{4})\.json$', name)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def date_problem(prefix: str, start: int, date: str) -> Optional[str]:
    """Why a northern-hemisphere date can't belong to a season starting in
    ``start`` (Aug start..Jul next year), or None."""
    if prefix not in NORTHERN or start == COVID_SEASON:
        return None
    try:
        year, month = int(str(date)[:4]), int(str(date)[5:7])
    except ValueError:
        return None
    expected = start if month >= 8 else start + 1
    if year != expected:
        return f"dated {str(date)[:10]} but the season starting {start} has {'Aug-Dec' if month >= 8 else 'Jan-Jul'} in {expected}"
    return None


def shift_late_autumn(matches: List[dict], start: int) -> int:
    n = 0
    for m in matches:
        d = str(m.get('date', ''))
        if len(d) >= 7 and d[:4].isdigit() and int(d[5:7]) >= 8 and int(d[:4]) == start + 1:
            m['date'] = f"{start}{d[4:]}"
            n += 1
    return n


def _window(season: int) -> Tuple[str, str]:
    return f"{season}-08-01", f"{season + 1}-07-31"


def _index(events: List[dict]):
    idx = collections.defaultdict(list)
    for e in events:
        idx[(e['home_score'], e['away_score'])].append(e)
    return idx


def _pair(match: dict, idx, window: Tuple[str, str]) -> Optional[dict]:
    h, a = match['home'], match['away']
    if h.get('score') is None or a.get('score') is None:
        return None
    found = [e for e in idx.get((h['score'], a['score']), [])
             if window[0] <= e['date'] <= window[1]
             and same_team(h.get('team', ''), e['home']) and same_team(a.get('team', ''), e['away'])]
    return found[0] if len(found) == 1 else None


def repair_from_espn(matches: List[dict], events: List[dict], labelled_start: int) -> Tuple[int, int, int, int]:
    """Give every match the right year. Returns (true season start, matches
    re-dated, confirmed by ESPN, disagreeing with ESPN).

    The month, day and time in these files are right and only the year is wrong
    (all 809 matches ESPN could pair agreed on month and day), so the year
    comes from the season: August-December in its first year, January-July in
    the next. ESPN identifies which season the file really holds (the one in
    which most matches pair on teams and score) and then cross-checks each
    corrected date.
    """
    idx = _index(events)
    best, best_n = labelled_start, -1
    for s in range(labelled_start - 1, labelled_start + 3):
        n = sum(1 for m in matches if _pair(m, idx, _window(s)))
        if n > best_n:
            best, best_n = s, n
    fixed = confirmed = disagree = 0
    for m in matches:
        old = str(m.get('date', ''))
        if len(old) < 10 or not old[:4].isdigit():
            continue
        year = best if int(old[5:7]) >= 8 else best + 1
        m['date'] = f"{year}{old[4:]}"
        fixed += 1
        e = _pair(m, idx, _window(best))
        if e is not None:
            confirmed += e['date'] == m['date'][:10]
            disagree += e['date'] != m['date'][:10]
    return best, fixed, confirmed, disagree


def fix_directory(directory: Path, dry_run: bool = False, use_espn: bool = True) -> List[dict]:
    """Apply both repairs. Returns one report row per changed file."""
    directory = Path(directory)
    report: List[dict] = []
    plans = []
    espn_cache: Dict[Tuple[int, int], List[dict]] = {}
    for path in sorted(directory.glob('*.json')):
        info = season_of(path.name)
        if not info or info[0] not in NORTHERN:
            continue
        prefix, start, _ = info
        try:
            matches = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(matches, list) or not matches:
            continue
        row = {'file': path.name, 'shifted': 0, 'redated': 0, 'confirmed': 0, 'disagree': 0, 'renamed_to': None}
        years = [int(str(m.get('date', ''))[:4]) for m in matches if str(m.get('date', ''))[:4].isdigit()]
        all_out = bool(years) and all(y not in (start, start + 1) for y in years)
        true_start = start
        if all_out and use_espn and prefix in ESPN_LEAGUES:
            slug = ESPN_LEAGUES[prefix]['slug']
            events: List[dict] = []
            for y in range(start - 1, start + 4):
                if (slug, y) not in espn_cache:
                    espn_cache[(slug, y)] = fetch_events(slug, y)
                    import time; time.sleep(REQUEST_PAUSE)
                events += espn_cache[(slug, y)]
            true_start, row['redated'], row['confirmed'], row['disagree'] = repair_from_espn(matches, events, start)
        else:
            row['shifted'] = shift_late_autumn(matches, start)
        if true_start != start:
            row['renamed_to'] = f"{prefix}-{true_start}-{true_start + 1}.json"
        if row['shifted'] or row['redated'] or row['renamed_to']:
            plans.append((path, matches, row))
    if not dry_run:
        # write first, then rename highest target first so a shifted file never lands on one not yet moved
        for path, matches, row in plans:
            path.write_text(json.dumps(matches, indent=2))
        moves = [(p, row['renamed_to']) for p, _, row in plans if row['renamed_to']]
        for path, target in sorted(moves, key=lambda x: x[1], reverse=True):
            dest = path.parent / target
            if dest.exists() and not any(p == dest for p, _ in moves):
                raise FileExistsError(f"cannot rename {path.name} to {target}: it exists")
            path.rename(dest)
    report = [row for _, _, row in plans]
    return report
