"""
Match information.
"""

import ast
import json, yaml

import pandas as pd
import numpy as np

from flask import url_for

from .player import Player
from .scores import Scores
from .utils import json_serial, total_time_from_ranges
from .team import Team

class Match(object):

    def __init__(self, row, tournament=None):
        """
        A row from the JSON data file.
        """


        if row['home']['score'] in ["C", "P", ""]:
            self.score = {"home": float("nan"), "away": float("nan")}

        else:
            self.score = {"home": float(row['home']['score']),
                          "away": float(row['away']['score'])}

        if isinstance(row['home']['team'], dict):
            self.teams = {'home': Team.from_dict(row['home']['team']),
                          'away': Team.from_dict(row['away']['team'])}
        elif tournament and hasattr(tournament, "teams_dict"):
            self.teams = {'home': tournament.teams_dict[row['home']['team']],
                          'away': tournament.teams_dict[row['away']['team']]
                     }
        else:
            self.teams = {'home': row['home']['team'],
                          'away': row['away']['team']
            }
        try:
            self.date =  row["date"].to_datetime()
        except AttributeError:
            self.date = pd.to_datetime(row["date"])

        if "stadium" in row:
            self.stadium = row["stadium"]
        if hasattr(row, "tround"):
            self.round = row['tround']

        # Store tournament metadata
        if not isinstance(tournament, type(None)):
            self.season = tournament.season
            self.tournament = tournament.name
        elif "season" in row:
            self.season = row['season']
            self.tournament = row['tournament']
        else:
            self.season = None
            self.tournament = None
            
        # Handle the lineups
        if "lineup" in row['home']:
            self.lineups = {'home': Lineup(row['home']['lineup']),
                            'away': Lineup(row['away']['lineup'])
            }
        else:
            self.lineups = None

        if "scores" in row['home']:
            # Handle the scores
            self.scores = {'home': Scores(row['home']['scores']),
                           'away': Scores(row['away']['scores'])
            }
            for i, score in self.scores['home'].scores.iterrows():
                if score['player']==None:
                    continue
                self.scores['home'].scores.at[i, 'player'] = (self.find_player(score['player']))
            for i, score in self.scores['away'].scores.iterrows():
                self.scores['away'].scores.at[i, 'player'] = (self.find_player(score['player']))
                
        else:
            self.scores = None
        try:
            self.url = row.url
        except:
            self.url = None

    def find_player(self, search):
        if self.lineups:
            for i, player in pd.concat([self.lineups['home'].lineup, self.lineups['away'].lineup]).iterrows():
                if search in player['name']: 
                    return player['name']
                else:
                    return None
            
    def all_scores(self):
        """
        Get a list of all of the scoring events in this match.
        """
        scores = self.scores['home'].scores.append(self.scores['away'].scores)
        return Scores(scores)

    def to_dict(self):
        """
        Serialise this match object in a dict.
        """
        data = {}
        data['date'] = self.date.isoformat()
        data['stadium'] = self.stadium
        if hasattr(self, "tournament"):
            data['tournament'] = self.tournament
            data['season'] = self.season
        for state in ["home", "away"]:
            data[state] = {}
            if isinstance(self.teams[state], Team):
                data[state]['team'] = self.teams[state].to_dict()
            else:
                data[state]['team'] = self.teams[state]
            data[state]['score'] = self.score[state]

            if hasattr(self, "lineups"):
                data[state]['lineup'] = self.lineups[state].to_dict()
            if hasattr(self, "scores") and self.scores != None:
                data[state]['scores'] = self.scores[state].to_dict()

        return data

    def to_json(self, filename=None):
        """Serialise this object in JSON format."""
        if filename:
            with open(filename, "w") as f:
                json.dump(self.to_dict(), f, default=json_serial)
        else:
            return json.dumps(self.to_dict(), default=json_serial)
    

    def to_yaml(self, filename=None):
        """Serialise this object in YAML format."""
        if filename:
            with open(filename, "w") as f:
                yaml.safe_dump(self.to_dict(), stream=f)
        else:
            return yaml.safe_dump(self.to_dict())

    def to_rest(self):
        home = self.teams['home'].short_name
        away = self.teams['away'].short_name

        if pd.isna(self.score['home']):
                score = None
        else:
            score = self.score
        
        return dict(date=self.date, 
                    season=self.season,
                    tournament=self.tournament,
                    url=url_for("match", home=home, away=away,
                                date=f"{self.date:%Y-%m-%d}",
                                _external=False),
                    lineups=url_for("lineup", home=home, away=away, date=f"{self.date:%Y-%m-%d}", _external=False),
                    events=url_for("events", home=home, away=away, date=f"{self.date:%Y-%m-%d}", _external=False), 
                    stadium=None,
                    
                    score = score,
                    home={"name": home,
                          "url": url_for("team", shortname=home, _external=False)}, 
                    away={"name": away,
                          "url": url_for("team", shortname=away,  _external=False)})
        
    @classmethod
    def from_json(cls, file):
        """
        Create a match from a json file.
        """
        with open(file, "r") as f:
            data = json.load(f)
        data = pd.DataFrame.from_dict([data]).iloc[0]

        return cls(data)

    @classmethod
    def from_yaml(cls, file):
        """
        Create a match from a yaml file.
        """
        with open(file, "r") as f:
            data = yaml.safe_load(f)
        data = pd.DataFrame.from_dict([data]).iloc[0]
        return cls(data)

    # @classmethod
    # def from_dict(cls, data):
    # """
    # Create a match from a dictionary.

    # Parameters
    # ----------
    # data : dict
    #    The dictionary containing the match data.
    # """
    
    
    
    def players(self):
        """
        Get a list of all of the players named in the lineups.
        """
        players = []
        players += self.lineups['home'].players()
        players += self.lineups['away'].players()
        return players

    def player_covariance(self):
        """
        Get the "covariance matrix" for players in this match.
        """
        matrix_for = np.zeros((len(self.lineups['home'].players()), len(self.lineups['away'].players())))
        matrix_against = np.zeros((len(self.lineups['home'].players()), len(self.lineups['away'].players())))
        for i, player1 in enumerate(self.lineups['home'].players()):
            for j, player2 in enumerate(self.lineups['away'].players()):
                matrix_for[i,j], matrix_against[i,j] = player1.onfield_point_mutual_rate(player2, self)
        return matrix_for, matrix_against
            
    def __repr__(self):
        layout = f"""{self.date:%Y-%m-%d %H:%M} {self.teams['home']} {self.score['home']:>3} v {self.score['away']:<3} {self.teams['away']}"""
            
        return layout

    def _repr_html_(self):
        """
        HTML Representation
        """
        if self.scores!=None:
            layout ="""<h2> {a.scores[home].total}\t{a.teams[home]} - {a.teams[away]}\t{a.scores[away].total} </h2>"""
            layout +="""
        <h3> {a.date:%Y-%m-%d %H:%M}</h3>
        <table>
        <tr>
        <td> {a.lineups[home].html} </td>
        <td> {a.scores[home].html} </td>
        <td> {a.scores[away].html} </td>
        <td> {a.lineups[away].html} </td>
        </tr>
        </table>"""
        else:
            layout ="""<h2> {a.teams[home]} - {a.teams[away]}</h2> <h3> {a.date:%Y-%m-%d %H:%M}</h3>"""
        return layout.format(a=self)



class Lineup(object):
    def __init__(self, data):
        """
        Represent a team's lineup
        """
        self.lineup = pd.DataFrame.from_dict(data, orient='index')
        # print(self.lineup.name.values)
        self.lineup.index = np.array(self.lineup.index, dtype=int)
        self.lineup.sort_index(inplace=True)
        
        self.lineup['game time'] = 0
        self.time_ranges = {}
        for key, value in self.lineup.iterrows():
            time_range, total_time = self._time_ranges(value)
            if pd.isna(total_time): total_time = 0
            self.lineup.at[key, 'game time'] = total_time
            self.time_ranges[value['name']] = time_range

    @classmethod
    def _time_ranges(cls, value):
        """
        Determine the time ranges for a given player.
        """

        time = []
        total_time = 0

        if isinstance(value['on'], (str)):
            value['on'] = ast.literal_eval(value['on'])

        if isinstance(value['off'], (str)):
            value['off'] = ast.literal_eval(value['off'])

        if isinstance(value['on'], (type(None), int, float)):
            if isinstance(value['on'], type(None)):
                value['on'] = "NaN"
                value['on'] = [float(value['on'])]
            else:
                value['on'] = [float(value['on'])]

        if isinstance(value['off'], (type(None), int, float)):
            if isinstance(value['off'], type(None)):
                value['off'] = "NaN"
                value['off'] = [float(value['off'])]
            else:
                value['off'] = [float(value['off'])]

        if not pd.isna(value['on']).any() and not pd.isna(value['off']).any() and len(value['on'])>len(value['off']):
            value['off'] += [80]

        try:
            if not pd.isna(value['on']).any() and pd.isna(value['off']).any():
                value['off'] = [80]
        except:
            print(value)

        try:
            if len(value['on'])<len(value['off']): value['off']+=[80]
        except TypeError:
            print(value)
        subs = sorted(value['on'] + value['off'])
        if len(subs)%2: subs.append(80)
        return total_time_from_ranges(subs)

    def player_covariance(self):
        """
        Get the "covariance matrix" for players in this lineup.
        """
        players = self.players()
        matrix = np.zeros((len(players), len(players)))
        for i, player1 in enumerate(players):
            for j, player2 in enumerate(players):
                if i==j: 
                    matrix[i,j] = np.nan
                if i<j:
                    matrix[i,j] = player1.onfield_point_mutual_rate(player2, self)[0]
                if i>j:
                    matrix[i,j] = - player1.onfield_point_mutual_rate(player2, self)[1]
        return matrix
    
    def players(self):
        players = [Player(**dict(player)) for i, player in self.lineup.iterrows()]
        return players

    def to_dict(self):
        """Represent this lineup as a dict."""
        return self.lineup[['name', 'on', 'off', 'reds', 'yellows']].T.to_dict()
    
    
    def __repr__(self):
        out = []
        for key, value in self.lineup.iterrows():
            out.append("{a}\t{b[name]}\t{b[game time]}".format(a=key, b=value))
            if key == 15:
                out.append("---"*5)
        return ("\n").join(out) #, "\n")
    
    
    @property
    def html(self):
        out = []
        header = """
        <tr><th>Pos</th><th>Player</th><th>Play time</th></tr>
        """
        for key, value in self.lineup.iterrows():
            
            time = []
            #subs = value['game time'].split(",")
            #for sub in value['game time']:
            #    time.append("{}→{}".format(sub[0], sub[1]))
                    
            value['game time rep']= " ".join(time)
            
            if key == 15: 
                out.append('<tr style="border-bottom: 1px solid #000;"><td>{a}</td><td>{b[name]}</td><td>{b[game time]}</td></tr>'.format(a=key, b=value))
            else:
                out.append("<tr><td>{a}</td><td>{b[name]}</td><td>{b[game time]}</td></tr>".format(a=key, b=value))
        return "<table>" +  header + ("\n").join(out) + "</table>" #, "\n")
    
    def _repr_html_(self):
        return self.html
