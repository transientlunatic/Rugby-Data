"""Tests for data_loader utilities."""

import json
import pytest
from pathlib import Path

from rugby.data_loader import find_json_files, load_tournament


@pytest.fixture
def data_dir(tmp_path):
    """Temporary directory with some fake JSON files."""
    (tmp_path / "celtic_2024-2025.json").write_text("{}")
    (tmp_path / "celtic_2025-2026.json").write_text("{}")
    (tmp_path / "premiership_2025-2026.json").write_text("{}")
    (tmp_path / "six-nations_2025-2026.json").write_text("{}")
    return tmp_path


@pytest.fixture
def minimal_tournament_json(tmp_path):
    """A minimal valid tournament JSON file."""
    data = {
        "name": "Test League",
        "season": "2025-2026",
        "matches": [
            {
                "home": {
                    "team": {
                        "name": "Team A",
                        "colors": {},
                        "short name": "A",
                        "country": "England",
                    },
                    "score": "20",
                    "scores": [],
                    "lineup": {},
                },
                "away": {
                    "team": {
                        "name": "Team B",
                        "colors": {},
                        "short name": "B",
                        "country": "England",
                    },
                    "score": "10",
                    "scores": [],
                    "lineup": {},
                },
                "date": "2025-09-01",
                "tround": 1,
                "season": "2025-2026",
                "tournament": "Test League",
            }
        ],
    }
    path = tmp_path / "test_2025-2026.json"
    path.write_text(json.dumps(data))
    return tmp_path


class TestFindJsonFiles:
    def test_finds_all_files(self, data_dir):
        files = find_json_files(data_dir)
        assert len(files) == 4

    def test_filter_by_league(self, data_dir):
        files = find_json_files(data_dir, league="celtic")
        assert len(files) == 2
        assert all("celtic" in f.name for f in files)

    def test_filter_by_season(self, data_dir):
        files = find_json_files(data_dir, season="2025-2026")
        assert len(files) == 3
        assert all("2025-2026" in f.name for f in files)

    def test_filter_league_and_season(self, data_dir):
        files = find_json_files(data_dir, league="celtic", season="2025-2026")
        assert len(files) == 1
        assert files[0].name == "celtic_2025-2026.json"

    def test_empty_dir(self, tmp_path):
        files = find_json_files(tmp_path)
        assert files == []

    def test_nonexistent_dir(self, tmp_path):
        files = find_json_files(tmp_path / "missing")
        assert files == []

    def test_returns_sorted(self, data_dir):
        files = find_json_files(data_dir)
        names = [f.name for f in files]
        assert names == sorted(names)


class TestLoadTournament:
    def test_load_valid_tournament(self, minimal_tournament_json):
        t = load_tournament("test", "2025-2026", data_dir=minimal_tournament_json)
        assert t is not None
        assert t.name == "Test League"
        assert t.season == "2025-2026"

    def test_load_missing_file_returns_none(self, tmp_path):
        t = load_tournament("nonexistent", "2025-2026", data_dir=tmp_path)
        assert t is None

    def test_tournament_has_played_matches(self, minimal_tournament_json):
        t = load_tournament("test", "2025-2026", data_dir=minimal_tournament_json)
        assert len(t.matches) == 1
        assert t.matches[0].score["home"] == 20.0
        assert t.matches[0].score["away"] == 10.0
