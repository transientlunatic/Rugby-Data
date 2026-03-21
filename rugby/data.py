"""
Public API for the rugby data package.

Imports the core data classes for convenient access:

    from rugby.data import Match, Tournament, Scores, Player, Team
"""

from .match import Match, Lineup
from .tournament import Tournament
from .scores import Scores
from .player import Player, Position
from .team import Team

__all__ = [
    "Match",
    "Lineup",
    "Tournament",
    "Scores",
    "Player",
    "Position",
    "Team",
]
