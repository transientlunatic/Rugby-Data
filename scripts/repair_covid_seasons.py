"""Repair the 2019-20 / 2020-21 files of the Premiership and both European
cups, which have the same fault the Celtic files had (see
``repair_celtic_seasons.py``):

* ``<comp>-2019-2020.json`` holds a copy of 2021-22 dated two years early
  (every match is in ``<comp>-2021-2022.json`` with the same teams and score).
  It is replaced.
* ``<comp>-2020-2021.json`` holds the real 2019-20 matches dated a year late,
  the autumn-2020 end of 2019-20 (dated correctly), and part of 2020-21.

Each 2020-21 row is paired with ESPN on teams and score: if ESPN dates it a
year earlier the year is corrected (month, day and time are kept), and rows
on or before the competition's 2019-20 end date (COVID pushed finals into
October 2020) move to 2019-20. Undated rows take ESPN's date. Rows ESPN can't
pair stay where they are and are reported. Afterwards fill the gaps with
``rugby data enrich-events -t <comp> --season <s> --add-missing``.

Run from the repository root: ``python scripts/repair_covid_seasons.py
premiership euro-champions euro-challenge``. It refuses a competition whose
2019-20 file is no longer a copy of 2021-22.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rugby.espn_sync import COVID_SEASON_END, load_matches, save_matches  # noqa: E402
from rugby.scrapers.espn import ESPN_LEAGUES, fetch_events, same_team  # noqa: E402

JSON = ROOT / 'json'


def key(m):
    return (m['home']['team'], m['away']['team'], m['home'].get('score'), m['away'].get('score'))


def espn_dates(m, events):
    return [e['date'] for e in events
            if (e['home_score'], e['away_score']) == (m['home'].get('score'), m['away'].get('score'))
            and same_team(m['home']['team'], e['home']) and same_team(m['away']['team'], e['away'])]


def repair(prefix):
    copy, mixed, later = (load_matches(JSON / f'{prefix}-{s}.json') for s in ('2019-2020', '2020-2021', '2021-2022'))
    in_later = {key(m) for m in later}
    shared = sum(key(m) in in_later for m in copy)
    if shared < 0.95 * len(copy):
        raise SystemExit(f'{prefix}-2019-2020.json: only {shared}/{len(copy)} rows are in 2021-22: already repaired?')

    slug = ESPN_LEAGUES[prefix]['slug']
    events = [e for y in (2019, 2020, 2021) for e in fetch_events(slug, y)]
    end = COVID_SEASON_END[prefix]
    s1920, s2021, unpaired, shifted = [], [], [], 0
    for m in mixed:
        d = str(m.get('date') or '')
        found = espn_dates(m, events) if m['home'].get('score') is not None else []
        if not d[:4].isdigit():
            if len(found) != 1:
                raise SystemExit(f'{prefix}: cannot date {key(m)} ({len(found)} ESPN candidates)')
            m['date'] = found[0] + 'T00:00:00'
        elif found:
            ours = date.fromisoformat(d[:10])
            gap = min(((date.fromisoformat(f) - ours).days for f in found), key=abs)
            if -367 <= gap <= -364:
                m['date'] = f'{int(d[:4]) - 1}{d[4:]}'
                shifted += 1
        else:
            unpaired.append(key(m))
        (s1920 if str(m['date'])[:10] <= end else s2021).append(m)

    save_matches(JSON / f'{prefix}-2019-2020.json', s1920)
    save_matches(JSON / f'{prefix}-2020-2021.json', s2021)
    print(f'{prefix}: dropped the 2021-22 copy ({len(copy)} rows); 2019-20 now {len(s1920)} '
          f'({shifted} re-dated a year earlier), 2020-21 now {len(s2021)}; '
          f'{len(unpaired)} rows ESPN could not pair: {unpaired[:5]}')


if __name__ == '__main__':
    for prefix in sys.argv[1:] or ['premiership', 'euro-champions', 'euro-challenge']:
        repair(prefix)
