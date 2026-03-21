"""Tests for the Scores class."""

import pytest
import pandas as pd
from rugby.scores import Scores


@pytest.fixture
def try_data():
    return [
        {"player": "Johnny Sexton", "type": "try", "value": 5, "minute": 10},
        {"player": "Johnny Sexton", "type": "conversion", "value": 2, "minute": 11},
        {"player": "Jordan Larmour", "type": "try", "value": 5, "minute": 35},
        {"player": "Johnny Sexton", "type": "penalty", "value": 3, "minute": 55},
        {"player": "Johnny Sexton", "type": "conversion", "value": 2, "minute": 70},
    ]


@pytest.fixture
def scores(try_data):
    return Scores(try_data)


class TestScoresCreation:
    def test_from_list(self, try_data):
        s = Scores(try_data)
        assert len(s.scores) == 5

    def test_empty_scores(self):
        s = Scores([])
        assert s.total == 0

    def test_total_computed(self, scores):
        # 5 + 2 + 5 + 3 + 2 = 17
        assert scores.total == 17

    def test_sorted_by_minute(self, scores):
        minutes = scores.scores["minute"].tolist()
        assert minutes == sorted(minutes)

    def test_cumulative_column(self, scores):
        cumulative = scores.scores["cumulative"].tolist()
        assert cumulative[-1] == scores.total


class TestScoresCount:
    def test_count_tries(self, scores):
        assert scores.count("try") == 2

    def test_count_conversions(self, scores):
        assert scores.count("conversion") == 2

    def test_count_penalties(self, scores):
        assert scores.count("penalty") == 1

    def test_count_missing_type(self, scores):
        assert scores.count("drop_goal") == 0


class TestScoresSerialisation:
    def test_to_dict(self, scores):
        d = scores.to_dict()
        assert isinstance(d, list)
        assert len(d) == 5
        assert "player" in d[0]
        assert "type" in d[0]
        assert "value" in d[0]
        assert "minute" in d[0]

    def test_repr_is_string(self, scores):
        assert isinstance(repr(scores), str)
