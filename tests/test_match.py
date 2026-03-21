"""Tests for the Match class."""

import math
import pytest
from rugby.match import Match


# Minimal match row matching the new LIST format used in Rugby-Data JSON files.
@pytest.fixture
def match_row():
    return {
        "home": {
            "team": {
                "name": "Leinster Rugby",
                "colors": {"primary": "blue"},
                "short name": "Leinster",
                "country": "Ireland",
            },
            "score": "24",
            "scores": [
                {"player": "Jordan Larmour", "type": "try", "value": 5, "minute": 10},
                {"player": "Johnny Sexton", "type": "conversion", "value": 2, "minute": 11},
                {"player": "Johnny Sexton", "type": "penalty", "value": 3, "minute": 25},
            ],
            "lineup": {
                "1": {"name": "Andrew Porter", "on": [0], "off": [80], "reds": 0, "yellows": 0},
                "10": {"name": "Johnny Sexton", "on": [0], "off": [80], "reds": 0, "yellows": 0},
                "14": {"name": "Jordan Larmour", "on": [0], "off": [80], "reds": 0, "yellows": 0},
            },
        },
        "away": {
            "team": {
                "name": "Munster Rugby",
                "colors": {"primary": "red"},
                "short name": "Munster",
                "country": "Ireland",
            },
            "score": "14",
            "scores": [
                {"player": "Simon Zebo", "type": "try", "value": 5, "minute": 30},
                {"player": "Jack Crowley", "type": "conversion", "value": 2, "minute": 31},
                {"player": "Jack Crowley", "type": "penalty", "value": 3, "minute": 60},
                {"player": "Jack Crowley", "type": "penalty", "value": 3, "minute": 70},
            ],
            "lineup": {
                "1": {"name": "Jeremy Loughman", "on": [0], "off": [80], "reds": 0, "yellows": 0},
                "10": {"name": "Jack Crowley", "on": [0], "off": [80], "reds": 0, "yellows": 0},
            },
        },
        "date": "2025-01-11",
        "tround": 5,
        "season": "2025-2026",
        "tournament": "United Rugby Championship",
    }


@pytest.fixture
def match(match_row):
    return Match(match_row)


class TestMatchCreation:
    def test_score_parsed(self, match):
        assert match.score["home"] == 24.0
        assert match.score["away"] == 14.0

    def test_teams_parsed(self, match):
        assert match.teams["home"].name == "Leinster Rugby"
        assert match.teams["away"].name == "Munster Rugby"

    def test_date_parsed(self, match):
        assert match.date is not None
        assert str(match.date.date()) == "2025-01-11"

    def test_season(self, match):
        assert match.season == "2025-2026"

    def test_tournament(self, match):
        assert match.tournament == "United Rugby Championship"

    def test_round(self, match):
        assert match.round == 5

    def test_lineups_present(self, match):
        assert match.lineups is not None
        assert "home" in match.lineups
        assert "away" in match.lineups

    def test_scores_present(self, match):
        assert match.scores is not None
        assert match.scores["home"].total == 10
        assert match.scores["away"].total == 13


class TestMatchWithFutureResult:
    """Match rows with no score (future fixtures)."""

    def test_empty_score_becomes_nan(self, match_row):
        match_row["home"]["score"] = ""
        match_row["away"]["score"] = ""
        m = Match(match_row)
        assert math.isnan(m.score["home"])
        assert math.isnan(m.score["away"])

    def test_cancelled_score(self, match_row):
        match_row["home"]["score"] = "C"
        match_row["away"]["score"] = "C"
        m = Match(match_row)
        assert math.isnan(m.score["home"])
