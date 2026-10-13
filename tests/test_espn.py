"""ESPN lineup adapter: roster conversion, event matching, and the replace policy.
No network: fetch functions are exercised through their pure helpers."""

import json
from pathlib import Path

from rugby import enrich
from rugby.scrapers import espn
from rugby.scrapers.espn import find_event, has_minutes, is_better, lineup_from_roster, same_team


def player(jersey, name, **extra):
    return {'jersey': str(jersey), 'athlete': {'displayName': name}, **extra}


def full_roster(prefix='P'):
    return [player(j, f'{prefix}{j}') for j in range(1, 24)]


class TestRoster:
    def test_starters_come_from_jersey_not_the_starter_flag(self):
        lu = lineup_from_roster([player(1, 'A', starter=False), player(15, 'B', starter=False),
                                 player(16, 'C', starter=True)])
        assert lu['1']['on'] == [0] and lu['15']['on'] == [0]
        assert lu['16']['on'] == []                        # bench, whatever ESPN's flag says
        assert lu['1'] == {'name': 'A', 'on': [0], 'off': [], 'reds': [], 'yellows': []}

    def test_bad_rows_are_dropped(self):
        lu = lineup_from_roster([player('x', 'A'), {'jersey': '2', 'athlete': {}}, player(3, 'B'), player(3, 'dup')])
        assert list(lu) == ['3'] and lu['3']['name'] == 'B'

    def test_fetch_lineups_needs_a_full_matchday_squad(self, monkeypatch):
        def fake(roster_h, roster_a):
            return {'rosters': [{'homeAway': 'home', 'roster': roster_h}, {'homeAway': 'away', 'roster': roster_a}]}
        monkeypatch.setattr(espn, '_get', lambda url, **p: fake(full_roster('H'), full_roster('A')))
        got = espn.fetch_lineups(1, 'e')
        assert len(got['home']) == 23 and got['away']['9']['name'] == 'A9'
        monkeypatch.setattr(espn, '_get', lambda url, **p: fake(full_roster('H')[:15], full_roster('A')))
        assert espn.fetch_lineups(1, 'e') is None          # no bench
        monkeypatch.setattr(espn, '_get', lambda url, **p: {})
        assert espn.fetch_lineups(1, 'e') is None


class TestMatching:
    def ev(self, date='2024-09-08', home='Stade Toulousain', away='Vannes', hs=30, as_=10):
        return {'id': '1', 'date': date, 'home': home, 'away': away, 'home_score': hs, 'away_score': as_}

    def match(self, home='Toulouse', away='Vannes', hs=30, as_=10, date='2024-09-08T14:00:00'):
        return {'date': date, 'home': {'team': home, 'score': hs}, 'away': {'team': away, 'score': as_}}

    def test_team_names(self):
        assert same_team('Reds', 'Queensland Reds')
        assert same_team('Bordeaux-Begles', 'Bordeaux Begles')
        assert same_team('Toulouse', 'Stade Toulousain')
        assert same_team('NSW Waratahs', 'New South Wales Waratahs')
        assert not same_team('Blues', 'Bulls')
        assert not same_team('', 'Reds')

    def test_finds_by_date_teams_and_scores(self):
        assert find_event(self.match(), [self.ev()])[0]['id'] == '1'

    def test_date_within_a_day_but_not_two(self):
        assert find_event(self.match(date='2024-09-09T00:00:00'), [self.ev()])[1] == 'ok'
        assert find_event(self.match(date='2024-09-10T00:00:00'), [self.ev()]) == (None, 'no_event')

    def test_wrong_scores_do_not_match(self):
        assert find_event(self.match(hs=31), [self.ev()]) == (None, 'score_mismatch')

    def test_swapped_orientation_is_reported_not_guessed(self):
        assert find_event(self.match(home='Vannes', away='Toulouse', hs=10, as_=30), [self.ev()]) == (None, 'swapped_orientation')

    def test_ambiguous_events_are_refused(self):
        assert find_event(self.match(), [self.ev(), self.ev()])[1] == 'ambiguous'


class TestPolicy:
    def lu(self, n, **p):
        return {str(j): {'name': f'p{j}', 'on': [0] if j <= 15 else [], 'off': [], 'reds': [], 'yellows': [], **p}
                for j in range(1, n + 1)}

    def test_missing_or_shorter_is_replaced(self):
        new = self.lu(23)
        assert is_better(None, new) and is_better({}, new)
        assert is_better(self.lu(15), new)
        assert not is_better(self.lu(23), new)

    def test_lineup_with_minutes_is_never_replaced(self):
        existing = self.lu(20)
        existing['3']['off'] = [55]
        assert has_minutes(existing) and not is_better(existing, self.lu(23))
        late = self.lu(20); late['17']['on'] = [60]
        assert has_minutes(late)
        assert not has_minutes(self.lu(23))


class TestEnrichSeason:
    def test_adds_lineups_and_tags_source(self, tmp_path, monkeypatch):
        m = {'date': '2024-03-02T08:00:00', 'home': {'team': 'Reds', 'score': 20}, 'away': {'team': 'Blues', 'score': 10}}
        (tmp_path / 'super-rugby-2024-2025.json').write_text(json.dumps([m, {**m, 'home': {'team': 'Reds', 'score': None}, 'away': {'team': 'Blues', 'score': None}}]))
        ev = [{'id': '9', 'date': '2024-03-02', 'home': 'Queensland Reds', 'away': 'Blues', 'home_score': 20, 'away_score': 10}]
        monkeypatch.setattr(enrich, 'fetch_events', lambda slug, y: ev)
        monkeypatch.setattr(enrich, 'fetch_lineups', lambda slug, eid: {'home': lineup_from_roster(full_roster('H')), 'away': lineup_from_roster(full_roster('A'))})
        monkeypatch.setattr(enrich, 'REQUEST_PAUSE', 0)

        stats = enrich.enrich_season('super-rugby', '2024-2025', tmp_path, dry_run=True)
        assert stats == {'matches': 1, 'added': 1}
        assert 'lineup' not in json.loads((tmp_path / 'super-rugby-2024-2025.json').read_text())[0]['home']   # dry run

        enrich.enrich_season('super-rugby', '2024-2025', tmp_path)
        out = json.loads((tmp_path / 'super-rugby-2024-2025.json').read_text())
        assert len(out[0]['home']['lineup']) == 23 and out[0]['lineup_source'] == 'espn'
        assert 'lineup' not in out[1]['home']                          # unplayed fixture untouched
        assert enrich.enrich_season('super-rugby', '2024-2025', tmp_path)['kept_existing'] == 1   # idempotent
