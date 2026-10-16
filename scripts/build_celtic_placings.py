"""Build final regular-season league placings for the Celtic League / Pro12 /
Pro14 / URC from the raw match files in ``json/``.

Writes ``dashboard/data/celtic_final_placings.json`` and (if the template is
present) ``dashboard/celtic_placings.html`` with the data embedded.

Standings use the usual 4/2/0 + losing-bonus (lost by <= 7) + try-bonus
(>= 4 tries) scheme, ordered by points, then wins, then points difference.
Playoffs are removed by capping each team at the regular-season game count.
Try bonuses can only be applied where try events were recorded (2011-12 on).
"""
import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Regular-season games per team. 2020-21 (conference format + Rainbow Cup) and
# 2002-03 (a single match) are not covered.
CAP = {'2003-2004': 22, '2004-2005': 20, '2005-2006': 20, '2006-2007': 20,
       '2007-2008': 18, '2008-2009': 18, '2009-2010': 18, '2010-2011': 22,
       '2011-2012': 22, '2012-2013': 22, '2013-2014': 22, '2014-2015': 22,
       '2015-2016': 22, '2016-2017': 22, '2017-2018': 21, '2018-2019': 21,
       '2019-2020': 18, '2021-2022': 18, '2022-2023': 18, '2023-2024': 18,
       '2024-2025': 18, '2025-2026': 18}

# Same franchise, different name / sponsor.
CANON = {'Borders': 'Border Reivers', 'Llanelli Scarlets': 'Scarlets',
         'Newport Gwent Dragons': 'Dragons RFC', 'DHL Stormers': 'Stormers',
         'Vodacom Bulls': 'Bulls', 'Hollywoodbets Sharks': 'Sharks',
         'Emirates Lions': 'Lions', 'Fidelity SecureDrive Lions': 'Lions'}
# Non-club fixtures that leak into some season files.
EXCLUDE = {'England', 'Canada Women', 'France Women', 'Ireland Women'}
SHORT = {'Leinster Rugby': 'Leinster', 'Munster Rugby': 'Munster', 'Ulster Rugby': 'Ulster',
         'Connacht Rugby': 'Connacht', 'Glasgow Warriors': 'Glasgow', 'Edinburgh Rugby': 'Edinburgh',
         'Cardiff Rugby': 'Cardiff', 'Dragons RFC': 'Dragons', 'Benetton Rugby': 'Benetton',
         'Zebre Parma': 'Zebre', 'Border Reivers': 'Borders'}


def tries(side):
    return sum(1 for e in (side.get('scores') or [])
               if str(e.get('type', '')).lower() == 'try')


def load(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        rows = [(d['date'][k], d['home'][k], d['away'][k], None) for k in d['home']]
    else:
        rows = [(x['date'], x['home'], x['away'], x.get('round_type')) for x in d]
    out = []
    for date, h, a, rt in rows:
        if h['score'] is None or a['score'] is None:
            continue
        name = lambda s: CANON.get(s['team'], s['team'])
        if name(h) in EXCLUDE or name(a) in EXCLUDE:
            continue
        out.append(dict(date=str(date), rt=rt, h=name(h), a=name(a), hs=h['score'], as_=a['score'],
                        ht=tries(h), at=tries(a), ev=bool(h.get('scores') or a.get('scores'))))
    return out


def table(matches, cap):
    if any(m['rt'] == 'league' for m in matches):
        matches = [m for m in matches if m['rt'] == 'league']
    matches = sorted(matches, key=lambda m: m['date'])
    n = collections.Counter()
    used = []
    for m in matches:
        if n[m['h']] >= cap or n[m['a']] >= cap:
            continue
        n[m['h']] += 1
        n[m['a']] += 1
        used.append(m)
    T = {}
    for m in used:
        for me, mf, oa, mt in ((m['h'], m['hs'], m['as_'], m['ht']), (m['a'], m['as_'], m['hs'], m['at'])):
            r = T.setdefault(me, dict(team=me, played=0, won=0, drawn=0, lost=0, pf=0, pa=0, points=0))
            r['played'] += 1
            r['pf'] += mf
            r['pa'] += oa
            if mf > oa:
                r['won'] += 1
                r['points'] += 4
            elif mf == oa:
                r['drawn'] += 1
                r['points'] += 2
            else:
                r['lost'] += 1
                r['points'] += 1 if oa - mf <= 7 else 0
            r['points'] += 1 if mt >= 4 else 0
    rows = sorted(T.values(), key=lambda r: (-r['points'], -r['won'], -(r['pf'] - r['pa'])))
    for i, r in enumerate(rows, 1):
        r['position'] = i
        r['short'] = SHORT.get(r['team'], r['team'])
    return rows, sum(m['ev'] for m in used) / max(1, len(used))


def main():
    seasons = []
    for season, cap in CAP.items():
        rows, tryfrac = table(load(ROOT / f'json/celtic-{season}.json'), cap)
        low = min(r['played'] for r in rows)
        status = 'complete' if low == cap else 'near' if low >= cap - 1 else 'partial'
        seasons.append(dict(season=season, status=status, games=cap, min_played=low,
                            try_bonus=tryfrac > 0.5, table=rows))
    out = ROOT / 'dashboard/data/celtic_final_placings.json'
    out.write_text(json.dumps(seasons, indent=1))
    tpl = ROOT / 'dashboard/celtic_placings.template.html'
    if tpl.exists():
        (ROOT / 'dashboard/celtic_placings.html').write_text(
            tpl.read_text().replace('/*DATA*/null', json.dumps(seasons)))
    for s in seasons:
        print(s['season'], s['status'], s['min_played'], [r['short'] for r in s['table'][:3]])


if __name__ == '__main__':
    main()
