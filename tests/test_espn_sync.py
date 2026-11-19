"""ESPN play-by-play -> scores/lineups, and season syncing. No network: the
fetch functions are replaced with canned data."""

import json

import pytest

from rugby import espn_sync, update
from rugby.scrapers import espn
from rugby.scrapers.espn import minute_of, same_team, timeline_detail

TEAM = 'http://x/leagues/1/seasons/2020/teams/{}?lang=en'
ATH = 'http://x/athletes/{}?lang=en'


BASE_ID = {'h': 1000, 'a': 2000}


def aid(code):
    """'h11' -> ESPN-style numeric athlete id for home jersey 11."""
    return str(BASE_ID[code[0]] + int(code[1:]))


def roster(team_id, side, prefix):
    return {'homeAway': side, 'team': {'id': team_id},
            'roster': [{'jersey': str(j), 'athlete': {'id': aid(f'{prefix}{j}'), 'displayName': f'{prefix.upper()} Player{j}'}}
                       for j in range(1, 24)]}


SUMMARY = {'rosters': [roster('10', 'home', 'h'), roster('20', 'away', 'a')]}


def play(kind, minute, team, athlete=None, period=1):
    p = {'type': {'text': kind}, 'clock': {'displayValue': minute, 'value': 0}, 'period': {'number': period},
         'team': {'$ref': TEAM.format(team)}}
    if athlete:
        p['participants'] = [{'athlete': {'$ref': ATH.format(aid(athlete))}}]
    return p


class TestTimeline:
    def test_minutes(self):
        assert minute_of({'displayValue': "23'"}) == 23
        assert minute_of({'displayValue': "80'+2"}) == 82
        assert minute_of({'value': 635.0}) == 11

    def test_scores_subs_and_cards(self):
        plays = [play('try', "10'", 20, 'a11'), play('conversion', "11'", 20, 'a10'),
                 play('penalty goal', "15'", 10, 'h10'), play('yellow card', "30'", 10, 'h3'),
                 play('player substituted', "55'", 10, 'h3', 2), play('substitute on', "55'", 10, 'h18', 2),
                 play('red card', "70'", 20, 'a5', 2), play('end of second half', "80'", 10)]
        d = timeline_detail(SUMMARY, plays, '2020-10-02')
        assert d['away']['scores'] == [{'minute': 10, 'type': 'Try', 'player': 'A Player11', 'value': 5},
                                       {'minute': 11, 'type': 'Conversion', 'player': 'A Player10', 'value': 2}]
        assert d['home']['scores'] == [{'minute': 15, 'type': 'Penalty', 'player': 'H Player10', 'value': 3}]
        assert d['home']['lineup']['3'] == {'name': 'H Player3', 'on': [0], 'off': [55], 'reds': [], 'yellows': [30]}
        assert d['home']['lineup']['18']['on'] == [55]
        assert d['away']['lineup']['5']['reds'] == [70]

    def test_penalty_try_value_follows_the_2017_law_change(self):
        for date, value in (('2016-01-01', 5), ('2018-01-01', 7)):
            d = timeline_detail(SUMMARY, [play('penalty try', "23'", 10)], date)
            assert d['home']['scores'] == [{'minute': 23, 'type': 'Penalty Try', 'player': None, 'value': value}]

    def test_scorer_keeps_our_spelling_when_surnames_agree(self):
        existing = {'home': {'10': {'name': 'J. Player10'}, '11': {'name': 'Someone Else'}}}
        d = timeline_detail(SUMMARY, [play('try', "5'", 10, 'h10'), play('try', "6'", 10, 'h11')], '2020-01-01', existing)
        assert [s['player'] for s in d['home']['scores']] == ['J. Player10', 'H Player11']

    def test_no_rosters_no_detail(self):
        assert timeline_detail({'rosters': []}, [], '2020-01-01') is None


def test_sponsor_names_still_match():
    assert same_team('Fidelity SecureDrive Lions', 'Lions') and same_team('10bet Lions', 'Lions')
    assert same_team('Benetton Rugby', 'Benetton Treviso')
    assert not same_team('Blues', 'Bulls')


def event(eid, date, home, away, hs=None, as_=None, completed=True):
    return {'id': eid, 'date': date, 'home': home, 'away': away, 'home_score': hs, 'away_score': as_,
            'completed': completed, 'kickoff': f'{date}T19:35:00.000Z', 'venue': 'Ground', 'attendance': 0}


def match(date, home, away, hs=None, as_=None, **extra):
    return {'date': f'{date}T19:35:00.000Z', 'home': {'team': home, 'score': hs, 'scores': [], 'lineup': {}},
            'away': {'team': away, 'score': as_, 'scores': [], 'lineup': {}}, **extra}


@pytest.fixture
def fake_espn(monkeypatch):
    """Install canned ESPN events; every match's play-by-play is one home try
    and conversion (7 points)."""
    state = {'events': []}
    monkeypatch.setattr(espn, 'fetch_events', lambda slug, y, include_unplayed=False:
                        [e for e in state['events'] if e['date'].startswith(str(y))])
    monkeypatch.setattr(espn, 'fetch_summary', lambda slug, eid: SUMMARY)
    monkeypatch.setattr(espn, 'fetch_plays', lambda slug, eid:
                        [play('try', "10'", 10, 'h11'), play('conversion', "11'", 10, 'h10'),
                         play('player substituted', "50'", 10, 'h1'), play('substitute on', "50'", 10, 'h17')])
    monkeypatch.setattr(espn_sync, 'REQUEST_PAUSE', 0)
    return state


def write(tmp_path, matches, name='celtic-2024-2025.json'):
    (tmp_path / name).write_text(json.dumps(matches))
    return tmp_path / name


def read(tmp_path, name='celtic-2024-2025.json'):
    return json.loads((tmp_path / name).read_text())


class TestSync:
    def test_fills_events_and_lineups_only_when_they_add_up(self, tmp_path, fake_espn):
        write(tmp_path, [match('2024-10-04', 'Munster Rugby', 'Ospreys', 7, 0),
                         match('2024-10-05', 'Leinster Rugby', 'Scarlets', 10, 0)])
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0),
                               event('2', '2024-10-05', 'Leinster', 'Scarlets', 10, 0)]
        stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path)
        assert stats['events_added'] == 1 and stats['events_dont_add_up'] == 1
        good, bad = read(tmp_path)
        assert [s['type'] for s in good['home']['scores']] == ['Try', 'Conversion'] and good['events_source'] == 'espn'
        assert good['home']['lineup']['1']['off'] == [50] and good['lineup_source'] == 'espn'
        assert bad['home']['scores'] == [] and 'events_source' not in bad
        # second run: nothing new to fetch for the good match
        assert espn_sync.sync_season('celtic', '2024-2025', tmp_path).get('events_added', 0) == 0

    def test_existing_events_and_minute_lineups_are_kept(self, tmp_path, fake_espn):
        m = match('2024-10-04', 'Munster Rugby', 'Ospreys', 7, 0)
        m['home']['scores'] = [{'minute': 1, 'type': 'Try', 'player': 'Ours', 'value': 5},
                               {'minute': 2, 'type': 'Conversion', 'player': 'Ours', 'value': 2}]
        m['home']['lineup'] = {'1': {'name': 'Ours', 'on': [0], 'off': [60], 'reds': [], 'yellows': []}}
        write(tmp_path, [m])
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0)]
        espn_sync.sync_season('celtic', '2024-2025', tmp_path)
        out = read(tmp_path)[0]
        assert out['home']['scores'][0]['player'] == 'Ours' and out['home']['lineup']['1']['name'] == 'Ours'

    def test_adds_missing_with_neighbouring_round_and_fills_placeholders(self, tmp_path, fake_espn):
        write(tmp_path, [match('2024-10-04', 'Munster Rugby', 'Ospreys', 7, 0, round=3, round_type='league'),
                         match('2025-06-01', 'TBC', 'TBC', round=20, round_type='knockout')])
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0),
                               event('2', '2024-10-05', 'Leinster', 'Scarlets', 7, 3),
                               event('3', '2025-06-01', 'Leinster', 'Munster', 7, 6)]
        assert 'matches_added' not in espn_sync.sync_season('celtic', '2024-2025', tmp_path)   # needs add_missing
        stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True)
        assert stats['matches_added'] == 2 and stats['placeholders_filled'] == 1
        out = {m['home']['team']: m for m in read(tmp_path)}
        assert 'TBC' not in out
        added = [m for m in read(tmp_path) if m['date'].startswith('2024-10-05')][0]
        assert added['home']['team'] == 'Leinster Rugby' and added['round'] == 3 and added['round_type'] == 'league'
        final = [m for m in read(tmp_path) if m['date'].startswith('2025-06-01')][0]
        assert final['round_type'] == 'knockout' and final['home']['score'] == 7 and final['source'] == 'espn'

    def test_swapped_orientation_or_disputed_score_is_not_duplicated(self, tmp_path, fake_espn):
        write(tmp_path, [match('2024-10-04', 'Vodacom Bulls', 'DHL Stormers', 26, 30)])
        fake_espn['events'] = [event('1', '2024-10-04', 'Stormers', 'Bulls', 30, 26)]
        stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True)
        assert stats.get('already_here_differs') == 1 and len(read(tmp_path)) == 1

    def test_fixtures_results_and_rescheduling(self, tmp_path, fake_espn):
        write(tmp_path, [match('2024-10-04', 'Munster Rugby', 'Ospreys', round=3),
                         match('2024-11-01', 'Leinster Rugby', 'Scarlets', round=5)])
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0),
                               event('2', '2024-12-20', 'Leinster', 'Scarlets', completed=False),
                               event('3', '2024-12-21', 'Ulster', 'Zebre', completed=False)]
        stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True, fixtures=True)
        assert stats['results_added'] == 1 and stats['redated'] == 1 and stats['fixtures_added'] == 1
        out = {m['home']['team']: m for m in read(tmp_path)}
        assert out['Munster Rugby']['home']['score'] == 7 and out['Munster Rugby']['round'] == 3
        assert out['Leinster Rugby']['date'].startswith('2024-12-20') and out['Leinster Rugby']['round'] == 5
        assert out['Ulster Rugby']['home']['score'] is None

    def test_legacy_column_files_are_read_and_written_as_lists(self, tmp_path, fake_espn):
        m = match('2024-10-04', 'Munster Rugby', 'Ospreys', 7, 0)
        write(tmp_path, {k: {'0': v} for k, v in m.items()})
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0)]
        espn_sync.sync_season('celtic', '2024-2025', tmp_path)
        out = read(tmp_path)
        assert isinstance(out, list) and out[0]['events_source'] == 'espn'

    def test_never_played_zero_zero_is_ignored(self, tmp_path, fake_espn):
        write(tmp_path, [])
        fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 0, 0)]
        assert espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True) == {'no_espn_events': 1}


def test_season_windows():
    assert espn_sync.season_window('2024-2025', False) == ('2024-08-01', '2025-07-31')
    assert espn_sync.season_window('2019-2020', False) == ('2019-08-01', '2020-09-20')
    assert espn_sync.season_window('2020-2021', False) == ('2020-09-21', '2021-07-31')
    assert espn_sync.season_window('2024-2025', True) == ('2024-01-01', '2024-12-31')
    assert espn_sync.season_window('2019-2020', False, 'premiership') == ('2019-08-01', '2020-11-01')
    assert espn_sync.season_window('2020-2021', False, 'premiership') == ('2020-11-02', '2021-07-31')
    assert espn_sync.season_window('2020-2021', False, 'top14') == ('2020-08-01', '2021-07-31')


def test_new_file_uses_the_competitions_spellings(tmp_path, fake_espn):
    write(tmp_path, [match('2023-10-04', 'Munster Rugby', 'Ospreys', 7, 0)], name='celtic-2023-2024.json')
    fake_espn['events'] = [event('1', '2024-10-04', 'Munster', 'Ospreys', 7, 0)]
    espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True)
    out = read(tmp_path)[0]
    assert (out['home']['team'], out['away']['team']) == ('Munster Rugby', 'Ospreys')


class TestUpdateRouting:
    def test_without_app_id_espn_leagues_use_espn(self, tmp_path, monkeypatch):
        monkeypatch.delenv(update.INCROWD_APP_ID_ENV, raising=False)
        calls = []
        monkeypatch.setattr(update, 'sync_season', lambda *a, **k: calls.append((a, k)) or {'results_added': 2})
        stats = update.update_league_data('urc', '2026-2027', tmp_path)
        assert calls[0][0][:2] == ('celtic', '2026-2027') and calls[0][1]['fixtures'] is True
        assert stats['updated_matches'] == 2 and not stats['errors']

    def test_without_app_id_uncovered_leagues_warn_not_fail(self, tmp_path, monkeypatch):
        monkeypatch.delenv(update.INCROWD_APP_ID_ENV, raising=False)
        monkeypatch.setattr(update, 'fetch_with_retry', lambda *a, **k: pytest.fail('should not call InCrowd'))
        stats = update.update_league_data('pro-d2', '2026-2027', tmp_path)
        assert not stats['errors'] and 'app id' in stats['warnings'][0]

    def test_app_id_is_sent_to_incrowd_only(self, monkeypatch):
        seen = []

        class Resp:
            def raise_for_status(self):
                pass
        monkeypatch.setattr(update.requests, 'get', lambda url, timeout, headers: seen.append(headers) or Resp())
        monkeypatch.setenv(update.INCROWD_APP_ID_ENV, 'abc')
        update.fetch_with_retry('https://rugby-union-feeds.incrowdsports.com/v1/matches')
        update.fetch_with_retry('https://example.org/')
        assert seen == [{'X-APP-ID': 'abc'}, {}]


def test_unannounced_kickoff_does_not_overwrite_ours(tmp_path, fake_espn):
    write(tmp_path, [match('2024-11-01', 'Leinster Rugby', 'Scarlets'), match('2024-11-02', 'Munster Rugby', 'Ospreys')])
    tbc = event('1', '2024-11-01', 'Leinster', 'Scarlets', completed=False)
    tbc['kickoff'] = '2024-11-01T00:00:00.000Z'
    moved = event('2', '2024-11-02', 'Munster', 'Ospreys', completed=False)
    moved['kickoff'] = '2024-11-02T14:00:00.000Z'
    fake_espn['events'] = [tbc, moved]
    assert espn_sync.sync_season('celtic', '2024-2025', tmp_path, fixtures=True)['redated'] == 1
    out = {m['home']['team']: m['date'] for m in read(tmp_path)}
    assert out == {'Leinster Rugby': '2024-11-01T19:35:00.000Z', 'Munster Rugby': '2024-11-02T14:00:00.000Z'}


def test_awarded_walkover_is_marked_and_empty_rosters_are_not_lineups(tmp_path, fake_espn, monkeypatch):
    write(tmp_path, [])
    fake_espn['events'] = [event('1', '2024-12-18', 'Scarlets', 'Toulon', 28, 0)]
    monkeypatch.setattr(espn, 'fetch_plays', lambda slug, eid: [])
    monkeypatch.setattr(espn, 'fetch_summary', lambda slug, eid: {'rosters': [
        {'homeAway': 'home', 'team': {'id': '1'}, 'roster': []}, {'homeAway': 'away', 'team': {'id': '2'}, 'roster': []}]})
    stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True)
    out = read(tmp_path)[0]
    assert stats['awarded'] == 1 and out['status'] == 'awarded'
    assert out['home']['lineup'] == {} and 'lineup_source' not in out and 'lineups_added' not in stats


def test_same_result_on_another_date_is_not_added_again(tmp_path, fake_espn):
    write(tmp_path, [match('2025-05-10', 'Stade Francais', 'Racing 92', 19, 16)])
    fake_espn['events'] = [event('1', '2025-04-21', 'Stade Francais Paris', 'Racing 92', 19, 16)]
    stats = espn_sync.sync_season('celtic', '2024-2025', tmp_path, add_missing=True)
    assert stats.get('already_here_other_date') == 1 and len(read(tmp_path)) == 1
