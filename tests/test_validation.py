"""Validation of newly added/changed matches against a git baseline."""

import json
import subprocess
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from rugby.validation import ERROR, WARNING, check_match, summarise, validate_directory

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def match(home="Leinster Rugby", away="Munster Rugby", hs=20, as_=10, date="2026-10-03T14:00:00.000Z"):
    return {"date": date, "home": {"team": home, "score": hs}, "away": {"team": away, "score": as_}}


def rules(m):
    return {(sev, rule) for sev, rule, _ in check_match(m, NOW)}


class TestCheckMatch:
    def test_good_match_and_fixture_are_clean(self):
        assert rules(match()) == set()
        assert rules(match(hs=None, as_=None, date="2026-10-20T14:00:00Z")) == set()   # not yet played

    def test_each_rule(self):
        assert (ERROR, "blank_team") in rules(match(home=""))
        assert (ERROR, "blank_team") in rules(match(away="   "))
        assert (ERROR, "blank_team") in rules(match(home=None))
        assert (ERROR, "same_team") in rules(match(home="Leinster Rugby", away="Leinster Rugby"))
        assert (ERROR, "non_canonical") in rules(match(home="Leinster"))
        assert (ERROR, "half_result") in rules(match(hs=10, as_=None))
        assert (ERROR, "negative_score") in rules(match(hs=-1, as_=5))
        assert (ERROR, "bad_date") in rules(match(date="not a date"))
        assert (ERROR, "malformed") in rules({"date": "2026-10-03T14:00:00Z"})

    def test_nan_score_counts_as_no_score(self):
        assert rules(match(hs=float("nan"), as_=float("nan"), date="2026-10-20T14:00:00Z")) == set()

    def test_warnings(self):
        assert (WARNING, "scoreless") in rules(match(hs=0, as_=0))
        assert (WARNING, "future_result") in rules(match(date="2026-12-01T14:00:00Z"))
        assert not any(sev == ERROR for sev, _ in rules(match(hs=0, as_=0)))
        assert (WARNING, "missing_result") in rules(match(hs=None, as_=None))   # played 9 days ago


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "json").mkdir()
    git(tmp_path, "init", "-q")
    historical = [match(home="", away=""), match(home="", away=""), match(hs=0, as_=0, date="2020-05-01T00:00:00Z"),
                  match(home="Ulster Rugby", away="Connacht Rugby", date="2026-09-01T14:00:00Z")]
    write(tmp_path, historical)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "baseline")
    return tmp_path


def write(repo, matches, name="celtic-2026-2027.json"):
    (repo / "json" / name).write_text(json.dumps(matches, indent=2))


def current(repo):
    return json.loads((repo / "json" / "celtic-2026-2027.json").read_text())


class TestValidateDirectory:
    def test_unchanged_tree_reports_nothing_despite_historical_problems(self, repo):
        assert validate_directory(repo / "json", against="HEAD", now=NOW) == []

    def test_historical_problems_are_reported_by_a_full_audit(self, repo):
        rules_seen = {i.rule for i in validate_directory(repo / "json", every_match=True, now=NOW)}
        assert {"blank_team", "scoreless", "duplicate"} <= rules_seen

    def test_a_good_new_match_passes(self, repo):
        write(repo, current(repo) + [match(home="Edinburgh Rugby", away="Glasgow Warriors")])
        assert validate_directory(repo / "json", now=NOW) == []

    def test_a_bad_new_match_is_caught_and_old_ones_are_not(self, repo):
        write(repo, current(repo) + [match(home="Edinburgh", away="Glasgow Warriors")])
        issues = validate_directory(repo / "json", now=NOW)
        assert [(i.severity, i.rule) for i in issues] == [(ERROR, "non_canonical")]
        assert issues[0].file == "celtic-2026-2027.json" and "Edinburgh" in issues[0].match

    def test_a_new_blank_name_match_is_caught_even_though_old_ones_exist(self, repo):
        write(repo, current(repo) + [match(home="", away="", date="2026-10-10T14:00:00Z")])
        assert [i.rule for i in validate_directory(repo / "json", now=NOW) if i.severity == ERROR] == ["blank_team"]

    def test_an_edited_match_is_rechecked(self, repo):
        ms = current(repo)
        ms[3]["home"]["score"] = None            # result removed from one side only
        write(repo, ms)
        assert [i.rule for i in validate_directory(repo / "json", now=NOW)] == ["half_result"]

    def test_new_duplicate_is_caught(self, repo):
        ms = current(repo)
        write(repo, ms + [dict(ms[3], attendance=999)])      # same date and teams, different content
        assert "duplicate" in {i.rule for i in validate_directory(repo / "json", now=NOW)}

    def test_new_file_is_checked_in_full(self, repo):
        write(repo, [match(home="Bath", away="Sale Sharks")], name="premiership-2026-2027.json")
        issues = validate_directory(repo / "json", now=NOW)
        assert [i.rule for i in issues if i.file == "premiership-2026-2027.json"] == ["non_canonical"]

    def test_no_git_means_everything_is_checked(self, tmp_path):
        (tmp_path / "json").mkdir()
        write(tmp_path, [match(home="")])
        assert [i.rule for i in validate_directory(tmp_path / "json", now=NOW)] == ["blank_team"]


class TestCli:
    def invoke(self, monkeypatch, repo, *args):
        import rugby.commands.data as cmd
        monkeypatch.setattr(cmd, "find_data_dir", lambda: repo / "json")
        return CliRunner().invoke(cmd.data, ["validate", *args])

    def test_exit_codes(self, monkeypatch, repo):
        assert self.invoke(monkeypatch, repo).exit_code == 0
        write(repo, current(repo) + [match(home="", away="", date="2026-10-10T14:00:00Z")])
        bad = self.invoke(monkeypatch, repo)
        assert bad.exit_code == 1 and "blank_team" in bad.output

    def test_warnings_pass_unless_strict(self, monkeypatch, repo):
        write(repo, current(repo) + [match(hs=0, as_=0, date="2026-10-04T14:00:00Z", home="Cardiff Rugby", away="Dragons RFC")])
        assert self.invoke(monkeypatch, repo).exit_code == 0
        assert self.invoke(monkeypatch, repo, "--strict").exit_code == 1

    def test_full_audit_never_fails_the_run(self, monkeypatch, repo):
        assert self.invoke(monkeypatch, repo, "--all").exit_code == 0

    def test_step_summary_is_written(self, monkeypatch, repo, tmp_path):
        out = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out))
        write(repo, current(repo) + [match(home="", away="", date="2026-10-10T14:00:00Z")])
        self.invoke(monkeypatch, repo)
        assert "blank_team" in out.read_text()


def test_summarise_empty():
    assert "No problems" in summarise([])
