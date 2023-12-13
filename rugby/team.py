from itertools import chain
import pandas as pd

from .player import Player

class Team(): 
    
    def __init__(self, name, colors, short_name, country):
        self.name = name.strip()
        self.colors = colors
        self.short_name = short_name.strip()
        self.country = country

    @classmethod
    def from_dict(cls, data):
        """Assemble a team from a dictionary."""
        team = cls(data['name'], data['colors'], data['short name'], data['country'])
        return team

    def to_dict(self):
        """Serialise this object as a dictionary."""
        return {"name": self.name,
                "colors": self.colors,
                "country": self.country,
                "short name": self.short_name}
    
    def __repr__(self):
        return "{}".format(self.name)

    def __str__(self):
        return self.short_name
    
    def _repr_html_(self):
        output = f"<h2>{self.name}"
        for color in self.colors.values():
            output += "<span>"+self._svg_color(color)+"</span>"
        output += "</h2>"
        return output

    def _svg_color(self, color, size=20):
        """Produce a colored circle."""
        svg = f""" <svg height="{size}" width="{size}">
        <circle cx="{size/2}" cy="{size/2}" r="{size/2}" stroke="black" stroke-width="1" fill="{color}" />
        </svg> """
        return svg
    
    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        else:
            return self.name == other.name
    
    def __hash__(self):
        return self.name.__hash__()
    
    def matches(self, tournament, filts=None):
        if filts=="home":
            return [x for x in tournament.matches if (x.teams['home'] == self)]
        elif filts=="away":
            return [x for x in tournament.matches if (x.teams['away'] == self)]
        else:
            return [x for x in tournament.matches if (x.teams['home'] == self) or (x.teams['away'] == self)]
        
    def squad(self, tournament):
        positions = []
        positions += [x.lineups['away'].lineup for x in self.matches(tournament, filts="away")]
        positions += [x.lineups['home'].lineup for x in self.matches(tournament, filts="home")]
        positions = pd.concat(positions)
        players = [Player(player['name']) for i, player in positions['name'].reset_index().drop_duplicates().iterrows()]
        return players
