"""One-off repair of Celtic League files that hold the wrong season's matches.

Found in November 2026 and checked against ESPN's fixture list:

* ``celtic-2019-2020.json`` held the 2021-22 URC season (all 147 matches
  identical in teams and score to ``celtic-2021-2022.json``), dated two years
  early. It is replaced, not repaired.
* ``celtic-2020-2021.json`` held three things: the pre-COVID 2019-20 matches
  (Sky match ids below 96000) dated one year late, the Aug-Sep 2020 restart of
  2019-20 (dated correctly), and part of the real 2020-21 season. The first two
  become ``celtic-2019-2020.json``, as does one row with a 2020-21 Sky id that
  ESPN dates exactly a year earlier. Two rows had no date; ESPN supplies them.
* ``celtic-2012-2013.json`` held 50 matches from 2013-14 (Sky ids from 60000)
  dated one year early. They move to ``celtic-2013-2014.json``, which also
  loses two women's internationals that had strayed into it.

Only the year was wrong in the misdated rows; month, day and time are kept.
Run once from the repository root: ``python scripts/repair_celtic_seasons.py``.
It refuses to run if the files no longer look broken.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rugby.scrapers.espn import fetch_events, same_team  # noqa: E402

JSON = ROOT / 'json'
COVID_RESTART_END = '2020-09-20'   # 2019-20 final was 12 Sep 2020; 2020-21 began 2 Oct


def load(name):
    d = json.loads((JSON / name).read_text())
    if isinstance(d, dict):     # legacy column-oriented format
        d = [{c: d[c][k] for c in d} for k in d['home']]
    return d


def save(name, matches):
    matches = sorted(matches, key=lambda m: str(m.get('date') or ''))
    (JSON / name).write_text(json.dumps(matches, indent=2))


def sky_id(m):
    hit = re.search(r'/(\d+)$', m.get('url') or '')
    return int(hit.group(1)) if hit else None


def shift_year(m, years):
    d = str(m['date'])
    m['date'] = f"{int(d[:4]) + years}{d[4:]}"


def date_from_espn(m, events, lo, hi):
    hs, as_ = m['home']['score'], m['away']['score']
    found = [e for e in events if lo <= e['date'] <= hi and (e['home_score'], e['away_score']) == (hs, as_)
             and same_team(m['home']['team'], e['home']) and same_team(m['away']['team'], e['away'])]
    if len(found) != 1:
        raise SystemExit(f"cannot date {m['home']['team']} v {m['away']['team']} from ESPN ({len(found)} candidates)")
    return found[0]['date'] + 'T00:00:00'


def espn_says_a_year_earlier(m, events):
    """True if ESPN's only match with these teams and score is exactly a year
    before ours (one 2019-20 row with a 2020-21 Sky id)."""
    d = str(m['date'])[:10]
    found = [e['date'] for e in events if (e['home_score'], e['away_score']) == (m['home']['score'], m['away']['score'])
             and same_team(m['home']['team'], e['home']) and same_team(m['away']['team'], e['away'])]
    return found == [f"{int(d[:4]) - 1}{d[4:]}"]


def main():
    m1920, m2021, m2122 = load('celtic-2019-2020.json'), load('celtic-2020-2021.json'), load('celtic-2021-2022.json')
    key = lambda m: (m['home']['team'], m['away']['team'], m['home']['score'], m['away']['score'])  # noqa: E731
    if not {key(m) for m in m1920} <= {key(m) for m in m2122}:
        raise SystemExit('celtic-2019-2020.json is no longer a copy of 2021-22: already repaired?')

    events = fetch_events(270557, 2019) + fetch_events(270557, 2020)
    season1920, season2021 = [], []
    for m in m2021:
        sid = sky_id(m)
        if str(m.get('date')) in ('NaT', 'None', ''):
            m['date'] = date_from_espn(m, events, '2019-08-01', COVID_RESTART_END)
            season1920.append(m)
        elif sid is not None and sid < 96000:
            shift_year(m, -1)
            season1920.append(m)
        elif str(m['date']) < COVID_RESTART_END:
            season1920.append(m)
        elif espn_says_a_year_earlier(m, events):
            shift_year(m, -1)
            season1920.append(m)
        else:
            season2021.append(m)

    m1213, m1314 = load('celtic-2012-2013.json'), load('celtic-2013-2014.json')
    stray = [m for m in m1213 if (sky_id(m) or 0) >= 60000]
    keep1213 = [m for m in m1213 if (sky_id(m) or 0) < 60000]
    for m in stray:
        shift_year(m, +1)
    women = [m for m in m1314 if 'Women' in m['home']['team'] + m['away']['team']
             or {m['home']['team'], m['away']['team']} == {'Ireland Women', 'England'}]
    season1314 = [m for m in m1314 if m not in women] + stray

    save('celtic-2019-2020.json', season1920)
    save('celtic-2020-2021.json', season2021)
    save('celtic-2012-2013.json', keep1213)
    save('celtic-2013-2014.json', season1314)
    print(f"2019-20: {len(season1920)}  2020-21: {len(season2021)}  "
          f"2012-13: {len(keep1213)}  2013-14: {len(season1314)} (dropped {len(women)} women's internationals)")


if __name__ == '__main__':
    main()
