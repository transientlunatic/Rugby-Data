"""Canonical team names: lookup, byte-preserving file rewrite, write-time
normalisation, and a guard that the committed data stays canonical."""

import json
from pathlib import Path

import pytest

from rugby.team_names import (
    TEAM_NAME_ALIASES,
    canonical_filename,
    canonical_team_name,
    normalise_directory,
    normalise_match_teams,
    rewrite_team_names,
)
from rugby.update import get_match_key, save_data

REPO_JSON = Path(__file__).resolve().parent.parent / "json"


class TestCanonicalName:
    @pytest.mark.parametrize("raw,expected", [
        ("Leinster", "Leinster Rugby"),
        ("Cardiff Blues", "Cardiff Rugby"),
        ("Canterbury Crusaders", "Crusaders"),
        ("Crusaders |", "Crusaders"),
        ("Neath–Swansea Ospreys", "Ospreys"),
        ("Neath-Swansea Ospreys", "Ospreys"),
        ("Free State Cheetahs", "Cheetahs"),
        ("Toyota Cheetahs", "Cheetahs"),
        ("Glasgow ", "Glasgow Warriors"),
        ("Bedford Blues ", "Bedford Blues"),        # stray whitespace
        ("  Cornish Pirates", "Cornish Pirates"),
        ("Leinster Rugby", "Leinster Rugby"),        # already canonical
        ("Toulouse", "Toulouse"),                    # unknown names pass through
        ("", ""),
    ])
    def test_lookup(self, raw, expected):
        assert canonical_team_name(raw) == expected

    def test_none_passes_through(self):
        assert canonical_team_name(None) is None

    def test_idempotent_and_targets_are_fixed_points(self):
        for target in set(TEAM_NAME_ALIASES.values()):
            assert canonical_team_name(target) == target, f"{target!r} is itself aliased"
        for raw in TEAM_NAME_ALIASES:
            assert canonical_team_name(canonical_team_name(raw)) == canonical_team_name(raw)


class TestRewriteText:
    def test_changes_only_the_team_values(self):
        text = '{"home": {"team": "Leinster", "score": 10.0,  "x": [1,2]},\n  "away":{"team":"Cardiff Blues"}}'
        new, changed = rewrite_team_names(text)
        assert new == '{"home": {"team": "Leinster Rugby", "score": 10.0,  "x": [1,2]},\n  "away":{"team":"Cardiff Rugby"}}'
        assert changed == {"Leinster": 1, "Cardiff Blues": 1}

    def test_player_and_other_names_are_untouched(self):
        text = '{"player": "Leinster", "name": "Cardiff Blues", "team": "Munster"}'
        new, _ = rewrite_team_names(text)
        assert new == '{"player": "Leinster", "name": "Cardiff Blues", "team": "Munster Rugby"}'

    def test_unicode_escapes_are_handled(self):
        new, changed = rewrite_team_names('{"team": "Neath\\u2013Swansea Ospreys"}')
        assert json.loads(new) == {"team": "Ospreys"}
        assert changed == {"Neath–Swansea Ospreys": 1}

    def test_idempotent(self):
        once, _ = rewrite_team_names('{"team": "Leinster"}')
        twice, changed = rewrite_team_names(once)
        assert twice == once and changed == {}


class TestFilenames:
    def test_reversed_years_are_put_in_order(self):
        assert canonical_filename("top14-2011-2010.json") == "top14-2010-2011.json"
        assert canonical_filename("top14-2012-2011.json") == "top14-2011-2012.json"
        assert canonical_filename("euro-champions-2023-2024.json") == "euro-champions-2023-2024.json"
        assert canonical_filename("rugby-world-cup-2023.json") == "rugby-world-cup-2023.json"


class TestNormaliseDirectory:
    def make(self, tmp_path):
        (tmp_path / "celtic-2020-2021.json").write_text('[{"home": {"team": "Leinster"}, "away": {"team": "Munster Rugby"}}]')
        (tmp_path / "top14-2011-2010.json").write_text('[{"home": {"team": "Racing"}, "away": {"team": "Toulouse"}}]')
        return tmp_path

    def test_check_reports_without_writing(self, tmp_path):
        d = self.make(tmp_path)
        before = {p.name: p.read_text() for p in d.iterdir()}
        report = normalise_directory(d, check=True)
        assert set(report) == {"celtic-2020-2021.json", "top14-2011-2010.json"}
        assert report["top14-2011-2010.json"]["renamed_to"] == "top14-2010-2011.json"
        assert {p.name: p.read_text() for p in d.iterdir()} == before

    def test_rewrites_and_renames_then_is_clean(self, tmp_path):
        d = self.make(tmp_path)
        normalise_directory(d)
        assert sorted(p.name for p in d.iterdir()) == ["celtic-2020-2021.json", "top14-2010-2011.json"]
        assert json.loads((d / "top14-2010-2011.json").read_text())[0]["home"]["team"] == "Racing 92"
        assert normalise_directory(d, check=True) == {}

    def test_refuses_to_overwrite_on_rename(self, tmp_path):
        d = self.make(tmp_path)
        (d / "top14-2010-2011.json").write_text("[]")
        with pytest.raises(FileExistsError):
            normalise_directory(d)


class TestWriteTime:
    def test_normalise_match_teams(self):
        m = normalise_match_teams({"home": {"team": "Bath"}, "away": {"team": "Sale "}})
        assert (m["home"]["team"], m["away"]["team"]) == ("Bath Rugby", "Sale Sharks")

    def test_match_key_ignores_spelling_variants(self):
        a = {"date": "2024-01-06T15:00:00Z", "home": {"team": "Leinster"}, "away": {"team": "Munster"}}
        b = {"date": "2024-01-06T15:00:00Z", "home": {"team": "Leinster Rugby"}, "away": {"team": "Munster Rugby "}}
        assert get_match_key(a) == get_match_key(b)

    def test_save_data_writes_canonical_names(self, tmp_path):
        path = tmp_path / "celtic-2024-2025.json"
        save_data(path, [{"home": {"team": "Edinburgh"}, "away": {"team": "Glasgow"}}])
        saved = json.loads(path.read_text())[0]
        assert (saved["home"]["team"], saved["away"]["team"]) == ("Edinburgh Rugby", "Glasgow Warriors")


@pytest.mark.skipif(not REPO_JSON.exists(), reason="no json/ directory")
def test_committed_data_is_canonical():
    """Fails if non-canonical names or reversed season filenames are committed.
    Fix with `rugby data normalise`."""
    report = normalise_directory(REPO_JSON, check=True)
    assert report == {}, f"{len(report)} file(s) not canonical; run `rugby data normalise`"
