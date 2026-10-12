"""Duplicate removal, void placeholders, and previous-season refresh."""

import json
from datetime import datetime

from click.testing import CliRunner

from rugby.cleanup import clean_directory, dedupe_matches, is_void_placeholder, mark_void
from rugby.update import LEAGUE_CONFIGS, seasons_to_update
from rugby.validation import WARNING, check_match

NOW = datetime(2026, 10, 12)


def m(home="Leinster Rugby", away="Munster Rugby", hs=20, as_=10, date="2026-03-01T14:00:00", **extra):
    out = {"date": date, "home": {"team": home, "score": hs}, "away": {"team": away, "score": as_}}
    out.update(extra)
    return out


class TestDedupe:
    def test_identical_rows_collapse(self):
        rows, n = dedupe_matches([m(), m()])
        assert len(rows) == 1 and n == 1

    def test_prefers_scored_then_richer_copy(self):
        fixture, result = m(hs=None, as_=None), m()
        assert dedupe_matches([fixture, result])[0] == [result]
        assert dedupe_matches([result, fixture])[0] == [result]
        detailed = m()
        detailed["home"]["lineup"] = {"1": {"name": "A"}}
        assert dedupe_matches([m(), detailed])[0] == [detailed]

    def test_tbc_and_unnamed_rows_are_never_merged(self):
        tbc = [m(home="TBC", away="TBC", hs=None, as_=None)] * 3
        unnamed = [m(home="", away="")] * 2
        rows, n = dedupe_matches(tbc + unnamed)
        assert len(rows) == 5 and n == 0

    def test_distinct_fixtures_kept(self):
        assert dedupe_matches([m(), m(date="2026-03-08T14:00:00")])[1] == 0


class TestVoid:
    def test_placeholder_detection(self):
        assert is_void_placeholder(m(hs=0, as_=0))
        assert not is_void_placeholder(m(hs=0, as_=1))
        detailed = m(hs=0, as_=0)
        detailed["home"]["lineup"] = {"1": {"name": "A"}}
        assert not is_void_placeholder(detailed)   # played: it has a lineup

    def test_mark_void_nulls_scores_and_sets_status(self):
        rows = [m(hs=0, as_=0), m()]
        assert mark_void(rows) == 1
        assert rows[0]["home"]["score"] is None and rows[0]["status"] == "void"
        assert "status" not in rows[1]

    def test_void_match_is_not_a_missing_result(self):
        old = m(hs=None, as_=None, date="2026-01-01T00:00:00Z")
        now = datetime(2026, 10, 12).astimezone()
        assert ("missing_result" in {r for _, r, _ in check_match(old, now)})
        assert "missing_result" not in {r for _, r, _ in check_match({**old, "status": "void"}, now)}
        assert all(sev == WARNING for sev, r, _ in check_match(old, now) if r == "missing_result")


class TestCleanDirectory(object):
    def test_idempotent_and_check_mode(self, tmp_path):
        (tmp_path / "x-2025-2026.json").write_text(json.dumps([m(), m(), m(date="2026-03-08T00:00:00", hs=0, as_=0)]))
        assert clean_directory(tmp_path, check=True) == {"x-2025-2026.json": {"duplicates": 1, "void": 1}}
        assert len(json.loads((tmp_path / "x-2025-2026.json").read_text())) == 3   # untouched
        clean_directory(tmp_path)
        assert clean_directory(tmp_path) == {}
        assert len(json.loads((tmp_path / "x-2025-2026.json").read_text())) == 2


class TestSeasonsToUpdate:
    cfg = LEAGUE_CONFIGS["premiership"]

    def write(self, tmp_path, rows):
        (tmp_path / "premiership-2025-2026.json").write_text(json.dumps(rows))

    def test_previous_season_included_while_results_missing(self, tmp_path):
        self.write(tmp_path, [m(hs=None, as_=None, date="2026-03-01T00:00:00")])
        assert seasons_to_update(self.cfg, NOW, tmp_path, "premiership") == ["2025-2026", "2026-2027"]

    def test_complete_void_or_future_previous_season_is_skipped(self, tmp_path):
        self.write(tmp_path, [m(), m(hs=None, as_=None, status="void"),
                              m(hs=None, as_=None, date="2026-10-12T00:00:00")])
        assert seasons_to_update(self.cfg, NOW, tmp_path, "premiership") == ["2026-2027"]

    def test_no_previous_file(self, tmp_path):
        assert seasons_to_update(self.cfg, NOW, tmp_path, "premiership") == ["2026-2027"]
