"""Summarise how complete the match data is for each competition.

Writes ``dashboard/data/data_coverage.json``: for every competition, the seasons
held and, over all matches with a recorded score, how many have only the score,
scoring events (scorers and score types), or a full lineup too.
"""
import collections
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = {
    'celtic': 'Celtic League / Pro12 / Pro14 / URC', 'premiership': 'Premiership',
    'top14': 'Top 14', 'pro-d2': 'Pro D2', 'championship': 'RFU Championship',
    'euro-champions': 'European Champions Cup', 'euro-challenge': 'European Challenge Cup',
    'super-rugby': 'Super Rugby', 'currie-cup': 'Currie Cup', 'npc': 'NPC',
    'japan-league-one': 'Japan League One', 'rugby-europe-championship': 'Rugby Europe Championship',
    'six-nations': 'Six Nations', 'mid-year-internationals': 'Mid-year internationals',
    'end-of-year-internationals': 'End-of-year internationals', 'rugby-world-cup': 'Rugby World Cup',
}


def sides(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        return [(d['home'][k], d['away'][k]) for k in d['home']]
    return [(x['home'], x['away']) for x in d]


def has_events(s):
    return bool(s.get('scores'))


def has_lineup(s):
    return bool(s.get('lineup'))


def main():
    comps = collections.defaultdict(list)
    for f in sorted(glob.glob(str(ROOT / 'json/*.json'))):
        m = re.match(r'(.+?)-(\d{4})(?:-(\d{4}))?\.json$', Path(f).name)
        comps[m.group(1)].append((m.group(2) + (f'-{m.group(3)}' if m.group(3) else ''), f))
    out = []
    for key, files in comps.items():
        n = events = lineups = 0
        seasons = []
        for season, f in files:
            sn = 0
            for h, a in sides(f):
                if h.get('score') is None or a.get('score') is None:
                    continue
                sn += 1
                n += 1
                events += has_events(h) or has_events(a)
                lineups += has_lineup(h) and has_lineup(a)
            if sn:
                seasons.append(season)
        if not n:
            continue
        out.append(dict(key=key, label=LABELS.get(key, key), first=seasons[0], last=seasons[-1],
                        seasons=len(seasons), matches=n, with_events=events, with_lineups=lineups))
    out.sort(key=lambda r: -r['matches'])
    (ROOT / 'dashboard/data/data_coverage.json').write_text(json.dumps(out, indent=1))
    for r in out:
        print(f"{r['label']:40s} {r['first']}..{r['last']} {r['seasons']:>3} seasons {r['matches']:>5} matches "
              f"events {r['with_events']/r['matches']:.0%} lineups {r['with_lineups']/r['matches']:.0%}")


if __name__ == '__main__':
    main()
