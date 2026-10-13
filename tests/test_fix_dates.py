"""Year-late dates: detection, the offline shift, and the ESPN-assisted repair."""

import json

from rugby.fix_dates import date_problem, fix_directory, repair_from_espn, season_of, shift_late_autumn
from rugby.validation import ERROR, validate_directory


def m(date, home='Toulouse', away='Clermont', hs=20, as_=10):
    return {'date': date, 'home': {'team': home, 'score': hs}, 'away': {'team': away, 'score': as_}}


class TestDetection:
    def test_season_of(self):
        assert season_of('top14-2017-2018.json') == ('top14', 2017, 2018)
        assert season_of('euro-champions-2019-2020.json') == ('euro-champions', 2019, 2020)
        assert season_of('summary.json') is None

    def test_dates_inside_the_season_are_fine(self):
        assert date_problem('top14', 2017, '2017-09-02T14:00:00') is None
        assert date_problem('top14', 2017, '2018-03-02') is None
        assert date_problem('top14', 2017, '2018-07-31') is None

    def test_autumn_in_the_wrong_year_is_flagged(self):
        assert date_problem('top14', 2017, '2018-12-30T14:00:00')
        assert date_problem('top14', 2017, '2019-06-03')            # the all-2019 files
        assert date_problem('top14', 2017, '2017-03-01')            # spring in the first year

    def test_other_competitions_and_the_covid_season_are_exempt(self):
        assert date_problem('super-rugby', 2020, '2021-12-30') is None   # calendar-year competition
        assert date_problem('premiership', 2019, '2020-10-31') is None   # 2019-20 ran into autumn 2020


class TestShift:
    def test_moves_only_autumn_dates_a_year_late(self):
        ms = [m('2018-12-30T14:00:00'), m('2017-09-02T14:00:00'), m('2018-03-10'), m('2018-08-01')]
        assert shift_late_autumn(ms, 2017) == 2
        assert [x['date'] for x in ms] == ['2017-12-30T14:00:00', '2017-09-02T14:00:00', '2018-03-10', '2017-08-01']

    def test_idempotent(self):
        ms = [m('2018-12-30')]
        shift_late_autumn(ms, 2017)
        assert shift_late_autumn(ms, 2017) == 0


class TestEspnRepair:
    def events(self):
        return [{'id': '1', 'date': '2011-09-10', 'home': 'Stade Toulousain', 'away': 'Clermont Auvergne', 'home_score': 20, 'away_score': 10},
                {'id': '2', 'date': '2012-03-03', 'home': 'Agen', 'away': 'Perpignan', 'home_score': 22, 'away_score': 17}]

    def test_finds_the_true_season_and_rebuilds_years(self):
        ms = [m('2019-09-10T19:00:00'), m('2019-03-03T15:00:00', 'Agen', 'Perpignan', 22, 7)]   # second has a different score
        season, fixed, confirmed, disagree = repair_from_espn(ms, self.events(), labelled_start=2010)
        assert season == 2011 and fixed == 2
        assert ms[0]['date'] == '2011-09-10T19:00:00' and ms[1]['date'] == '2012-03-03T15:00:00'
        assert (confirmed, disagree) == (1, 0)      # the mismatched score isn't paired, but still gets the right year


class TestFixDirectory:
    def test_dry_run_then_write_and_rename_without_collision(self, tmp_path):
        # two files each labelled a year early: 2010-2011 really holds 2011, 2011-2012 really holds 2012
        (tmp_path / 'celtic-2017-2018.json').write_text(json.dumps([m('2018-12-30'), m('2018-03-01')]))
        report = fix_directory(tmp_path, dry_run=True, use_espn=False)
        assert [r['file'] for r in report] == ['celtic-2017-2018.json'] and report[0]['shifted'] == 1
        assert json.loads((tmp_path / 'celtic-2017-2018.json').read_text())[0]['date'] == '2018-12-30'
        fix_directory(tmp_path, use_espn=False)
        assert json.loads((tmp_path / 'celtic-2017-2018.json').read_text())[0]['date'] == '2017-12-30'
        assert fix_directory(tmp_path, use_espn=False) == []                  # idempotent


class TestValidatorRule:
    def test_year_late_autumn_is_an_error_for_new_matches(self, tmp_path):
        (tmp_path / 'celtic-2025-2026.json').write_text(json.dumps([
            m('2025-10-04T14:00:00', 'Leinster Rugby', 'Munster Rugby'),
            m('2026-10-04T14:00:00', 'Ulster Rugby', 'Connacht Rugby')]))
        issues = validate_directory(tmp_path, against=None, now=None)
        bad = [i for i in issues if i.rule == 'season_date']
        assert len(bad) == 1 and bad[0].severity == ERROR and 'Ulster' in bad[0].match
