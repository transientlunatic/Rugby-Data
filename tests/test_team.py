"""Tests for the Team class."""

import pytest
from rugby.team import Team


@pytest.fixture
def team_data():
    return {
        "name": "Leinster Rugby",
        "colors": {"primary": "blue", "secondary": "white"},
        "short name": "Leinster",
        "country": "Ireland",
    }


@pytest.fixture
def team(team_data):
    return Team.from_dict(team_data)


class TestTeamCreation:
    def test_from_dict(self, team_data):
        t = Team.from_dict(team_data)
        assert t.name == "Leinster Rugby"
        assert t.short_name == "Leinster"
        assert t.country == "Ireland"

    def test_direct_constructor(self):
        t = Team("Munster Rugby", {"primary": "red"}, "Munster", "Ireland")
        assert t.name == "Munster Rugby"
        assert t.short_name == "Munster"

    def test_name_stripped(self):
        """Whitespace around names should be stripped."""
        t = Team("  Bath Rugby  ", {}, "  Bath  ", "England")
        assert t.name == "Bath Rugby"
        assert t.short_name == "Bath"


class TestTeamEquality:
    def test_equal_teams(self, team):
        other = Team("Leinster Rugby", {}, "Leinster", "Ireland")
        assert team == other

    def test_equal_to_string(self, team):
        assert team == "Leinster Rugby"

    def test_not_equal(self, team):
        other = Team("Munster Rugby", {}, "Munster", "Ireland")
        assert team != other

    def test_hashable(self, team):
        """Team should be usable as a dict key or set member."""
        team_set = {team}
        assert team in team_set


class TestTeamSerialisation:
    def test_to_dict_round_trip(self, team):
        d = team.to_dict()
        reconstructed = Team.from_dict(d)
        assert reconstructed.name == team.name
        assert reconstructed.short_name == team.short_name
        assert reconstructed.country == team.country

    def test_repr(self, team):
        assert "Leinster Rugby" in repr(team)

    def test_str(self, team):
        assert str(team) == "Leinster"
