"""Add or improve lineups from ESPN (see ``scrapers/espn.py`` for coverage and limits)."""

import collections
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from .scrapers.espn import (ESPN_LEAGUES, REQUEST_PAUSE, fetch_events, fetch_lineups,
                            find_event, is_better)


def season_years(season: str, calendar_year: bool) -> List[int]:
    start, end = (int(x) for x in season.split('-'))
    return [start] if calendar_year else [start, end]


def seasons_on_disk(json_dir: Path, prefix: str) -> List[str]:
    out = []
    for p in sorted(Path(json_dir).glob(f'{prefix}-*.json')):
        tail = p.stem[len(prefix) + 1:]
        if len(tail) == 9 and tail[4] == '-' and tail.replace('-', '').isdigit():
            out.append(tail)
    return out


def enrich_season(league: str, season: str, json_dir: Path, dry_run: bool = False,
                  events_cache: Optional[Dict] = None) -> Dict:
    """Fill or improve lineups for one file. Returns counts, including why
    matches were skipped."""
    cfg = ESPN_LEAGUES[league]
    path = Path(json_dir) / f'{league}-{season}.json'
    stats = collections.Counter()
    try:
        matches = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        stats['no_file'] = 1
        return dict(stats)
    if not isinstance(matches, list):
        stats['legacy_format'] = 1
        return dict(stats)

    events: List[dict] = []
    for y in season_years(season, cfg['calendar_year']):
        key = (cfg['slug'], y)
        if events_cache is not None and key in events_cache:
            events += events_cache[key]
            continue
        got = fetch_events(cfg['slug'], y)
        time.sleep(REQUEST_PAUSE)
        if events_cache is not None:
            events_cache[key] = got
        events += got

    changed = False
    for m in matches:
        if (m.get('home') or {}).get('score') is None or m.get('status') == 'void':
            continue
        stats['matches'] += 1
        existing = (m['home'].get('lineup'), m['away'].get('lineup'))
        event, why = find_event(m, events)
        if event is None:
            stats['skip_' + why] += 1
            continue
        # Only fetch the roster if it could matter: we have no complete lineup,
        # or ours has no minutes and might be shorter.
        if existing[0] and existing[1] and any(
                p.get('off') or p.get('reds') or p.get('yellows') for lu in existing for p in lu.values()):
            stats['kept_has_minutes'] += 1
            continue
        new = fetch_lineups(cfg['slug'], event['id'])
        time.sleep(REQUEST_PAUSE)
        if new is None:
            stats['skip_no_roster'] += 1
            continue
        if not (is_better(existing[0], new['home']) or is_better(existing[1], new['away'])):
            stats['kept_existing'] += 1
            continue
        stats['improved' if (existing[0] or existing[1]) else 'added'] += 1
        for side in ('home', 'away'):
            if is_better(m[side].get('lineup'), new[side]):
                m[side]['lineup'] = new[side]
        m['lineup_source'] = 'espn'
        changed = True

    if changed and not dry_run:
        path.write_text(json.dumps(matches, indent=2))
    return dict(stats)
