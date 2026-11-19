"""Add results a season file lacks from the season's Wikipedia page.

    python scripts/fill_from_wikipedia.py celtic 2006-2007 "2006–07 Celtic League"
    python scripts/fill_from_wikipedia.py celtic 2006-2007 "2006–07 Celtic League" --wikitext page.txt --dry-run

Results only (date, teams, score, venue, attendance): the older pages have no
minutes, so no scoring events or lineups are taken. A Wikipedia match counts
as already present when the file has the same two teams (either way round)
within a day of it; differing scores are reported, not changed. Added rows
carry ``"source": "wikipedia"``.

The page is read with ``index.php?action=raw`` (the API often rate-limits
shared addresses), retrying with back-off; ``--wikitext`` reads a saved copy.
The repository's ``extract_rugbybox_templates`` misses boxes outside the
usual round sections (rearranged midweek games), so boxes are found here by
matching braces and then parsed with the existing ``parse_rugbybox``.
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rugby.espn_sync import load_matches, resolve_team, save_matches  # noqa: E402
from rugby.scrapers.espn import same_team  # noqa: E402
from rugby.scrapers.six_nations import HEADERS, parse_rugbybox, transform_to_standard_format  # noqa: E402
from rugby.team_names import normalise_match_teams  # noqa: E402


def fetch_wikitext(title: str, attempts: int = 5) -> str:
    for i in range(attempts):
        r = requests.get('https://en.wikipedia.org/w/index.php', params={'title': title, 'action': 'raw'},
                         headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.text
        time.sleep(5 * (i + 1))
    raise SystemExit(f'could not fetch "{title}" (last status {r.status_code})')


def rugbyboxes(wikitext: str):
    """Every {{rugbybox ...}} template, nested templates included."""
    for m in re.finditer(r'\{\{\s*rugbybox\b', wikitext, re.I):
        depth, j = 0, m.start()
        while j < len(wikitext):
            if wikitext.startswith('{{', j):
                depth, j = depth + 1, j + 2
            elif wikitext.startswith('}}', j):
                depth, j = depth - 1, j + 2
                if depth == 0:
                    break
            else:
                j += 1
        yield wikitext[m.start():j]


def wiki_matches(wikitext: str):
    out = []
    for box in rugbyboxes(wikitext):
        parsed = parse_rugbybox(box)
        if not parsed:
            continue
        m = normalise_match_teams(transform_to_standard_format(parsed))
        if m['home'].get('score') is None or not str(m.get('date', ''))[:4].isdigit():
            continue
        for side in ('home', 'away'):
            m[side].setdefault('scores', [])
            m[side].setdefault('lineup', {})
        out.append(m)
    return out


def same_fixture(a, b):
    from datetime import date
    da, db = str(a.get('date', ''))[:10], str(b.get('date', ''))[:10]
    if not (da[:4].isdigit() and db[:4].isdigit()):
        return False
    if abs((date.fromisoformat(da) - date.fromisoformat(db)).days) > 1:
        return False
    ah, aa, bh, ba = a['home']['team'], a['away']['team'], b['home']['team'], b['away']['team']
    return (same_team(ah, bh) and same_team(aa, ba)) or (same_team(ah, ba) and same_team(aa, bh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prefix')
    ap.add_argument('season')
    ap.add_argument('title')
    ap.add_argument('--wikitext', help='read the page from this file instead of fetching it')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    path = ROOT / 'json' / f'{args.prefix}-{args.season}.json'
    ours = load_matches(path) or []
    text = Path(args.wikitext).read_text() if args.wikitext else fetch_wikitext(args.title)
    added, differ = [], []
    known = sorted({m[s]['team'] for m in ours for s in ('home', 'away')})
    for w in wiki_matches(text):
        for side in ('home', 'away'):        # write the spelling this file already uses
            w[side]['team'] = resolve_team(w[side]['team'], known)
        twin = next((m for m in ours if same_fixture(m, w)), None)
        if twin is None:
            w['source'] = 'wikipedia'
            added.append(w)
        elif {twin['home'].get('score'), twin['away'].get('score')} != {w['home']['score'], w['away']['score']}:
            differ.append((str(w['date'])[:10], w['home']['team'], w['away']['team'],
                           (twin['home'].get('score'), twin['away'].get('score')), (w['home']['score'], w['away']['score'])))
    print(f'{path.name}: {len(ours)} matches, {len(added)} added from Wikipedia')
    for d in differ:
        print('  score differs (ours, Wikipedia):', d)
    if added and not args.dry_run:
        save_matches(path, ours + added)


if __name__ == '__main__':
    main()
