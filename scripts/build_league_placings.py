"""Final regular-season placings for the double-round-robin leagues in the
data (Celtic/URC, Premiership, Top 14, Pro D2).

Writes ``dashboard/data/league_placings.json``. Reuses the table logic from
``build_celtic_placings`` (4/2/0 + bonus points, playoffs removed by capping each
team at the regular-season game count). Where a season has no explicit cap,
the cap is ``2 * (clubs - 1)``, a double round robin.
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_celtic_placings as bc  # noqa: E402

ROOT = bc.ROOT
LEAGUES = {
    'celtic': 'Celtic League / Pro12 / Pro14 / URC',
    'premiership': 'Premiership',
    'top14': 'Top 14',
    'pro-d2': 'Pro D2',
}
SKIP_SEASONS = {'celtic': {'2002-2003', '2020-2021', '2026-2027'}}


SUFFIX = re.compile(r' (Rugby|Tigers|Saints|Chiefs|Sharks|Falcons|Bears|Warriors)$')


def short(name):
    return bc.SHORT.get(name) or SUFFIX.sub('', name)


def prepare(league, season, matches):
    """Return (matches, cap) with clubs that left the league mid-season removed."""
    if league == 'celtic':
        return matches, bc.CAP.get(season)
    n = collections.Counter()
    for m in matches:
        n[m['h']] += 1
        n[m['a']] += 1
    if not n:
        return matches, None
    clubs = {t for t, c in n.items() if c >= 0.5 * max(n.values())}
    matches = [m for m in matches if m['h'] in clubs and m['a'] in clubs]
    return matches, 2 * (len(clubs) - 1)


def build():
    out = []
    for league, label in LEAGUES.items():
        seasons = []
        for f in sorted(glob.glob(str(ROOT / f'json/{league}-*.json'))):
            season = re.search(r'(\d{4}-\d{4})\.json$', f).group(1)
            if season in SKIP_SEASONS.get(league, ()):
                continue
            matches, cap = prepare(league, season, bc.load(f))
            if not matches or not cap:
                continue
            rows, tryfrac = bc.table(matches, cap)
            low = min(r['played'] for r in rows)
            if len(rows) < 4 or low < 0.5 * cap:
                # too little of the season to call it a placing; say so, because a club listed
                # under two names (a sponsor change) also lands here
                few = [r['team'] for r in rows if r['played'] < 0.5 * cap]
                print(f'skipping {league} {season}: fewest games {low} of {cap} ({few})', file=sys.stderr)
                continue
            for r in rows:
                r['short'] = short(r['team'])
            status = 'complete' if low == cap else 'near' if low >= 0.9 * cap else 'partial'
            seasons.append(dict(season=season, status=status, games=cap, min_played=low,
                                try_bonus=tryfrac > 0.5, table=rows))
        out.append(dict(league=league, label=label, seasons=seasons))
    return out


if __name__ == '__main__':
    data = build()
    (ROOT / 'dashboard/data/league_placings.json').write_text(json.dumps(data))
    for L in data:
        print(L['league'])
        for s in L['seasons']:
            print('  ', s['season'], s['status'], f"{s['min_played']}/{s['games']}", len(s['table']), [r['short'] for r in s['table'][:2]])
