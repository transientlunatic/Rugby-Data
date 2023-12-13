import ast

import pandas as pd
import numpy as np

from .match import *
from .tournament import *
from .scores import *
from .player import *
from .team import *


class Score():
    
    def __init__(self, match, player, type, value, minute):
        self.match = match
        self.player = Player(player)
        self.type = type
        self.value = value
        self.minute = minute


    def __repr__(self):
        return "{} by {} ({}-{})".format(self.type, self.player.name, self.match.home, self.match.away)



