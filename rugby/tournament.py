import ast
from itertools import chain

import pandas as pd
import numpy as np

import json

from .match import Match, Lineup
from .team import Team
from . import utils

class Tournament():
    """
    Represent a whole tournament.
    """
    
    def __init__(self, name, season, matches, teams=None):
        
        self.season=season
        self.name = name
        
        self.team_conferences = {}
        if teams: 
            self.teams_flat = list(chain(*teams.values()))
            self.team_list = [Team.from_dict(team) for team in self.teams_flat]
            cons = {}
            for conference, team_list in teams.items():
                for team in team_list:
                    #print(team, conference)
                    cons[team['short name']] = conference
            self.teams_dict = {team.short_name:team for team in self.team_list}
            self.team_conferences = cons
            
        if isinstance(matches, pd.DataFrame):
            self.matches = [Match(x, tournament=self) for i, x in matches.iterrows()]
        else:
            self.matches = [Match(x, tournament=self) for x in matches]
            
        self.future = [match for match in self.matches if (match.score==None) or (pd.isna(match.score['home']))]
        
        for match in self.future:
            self.matches.remove(match)
        
    @classmethod
    def from_json(cls, file):
        """
        Generate a Tournament from a JSON file.

        file : path
           The path of a JSON file containing the saved tournament data.
        """

        with open(file, "r") as f:
            data =json.load(f)

        matches = pd.DataFrame.from_dict(data['matches'])
        if "teams" in data.keys():
            teams = data['teams']
        else:
            teams = None
            
        return cls(data['name'], data['season'], matches, teams)

    @classmethod
    def from_csv(cls, file, name, season):
        """
        Generate a Tournament from a CSV file.
        """
        data = pd.read_csv(file)
        matches = utils.dense_table_to_nested(data)

        return cls(name, season, matches)

    def to_json(self, filename=None):
        """Serialise this tournament as a json."""
        data = {}
        data['name'] = self.name
        data['season'] = self.season
        if hasattr(self, "team_list"):
            data['teams'] = [team.to_dict() for team in self.team_list]
        data['matches'] = [match.to_dict() for match in self.matches]
        data['matches'] += [match.to_dict() for match in self.future]

        if filename:
            with open(filename, "w") as f:
                json.dump(data, f)
        else:
            return data

    def save_csv(self, file):
        """
        Save this tournament as a CSV.
        """
        rows = []
        for match in tournament.matches:
            for state in ("home", "away"):
                if not hasattr(match, 'lineups'):
                    rows.append([int(match.round), match.date, np.nan, np.nan, match.teams['home'], match.teams['away']])
                else:
                    match.lineups[state].lineup['position'] = match.lineups[state].lineup.index
                    match.scores[state].scores['ix'] = match.scores[state].scores.index
                    mega = pd.merge(
                    match.scores[state].scores.join(match.scores[state].scores.pivot(columns="type", values=["minute"], index=("ix"))), 
                    match.lineups[state].lineup, left_on='player', right_on='name', how='outer')
                    mega = mega.sort_values("position")
                    mega = mega.rename(columns={("minute", "conversion"): "conversion",
                                           ("minute", "penalty"): "penalty",
                                           ("minute", "try"): "tries",
                                            ("minute", "kick"): "kick"
                                           })
                    for column in ['kick', 'tries', 'penalty', 'conversion']:
                        if not column in mega.columns:
                            mega[column] = pd.Series()

                    for i, player in mega.fillna("").iterrows():
                        rows.append([int(match.round), match.date, match.scores['home'].total, match.scores['away'].total, match.teams['home'], match.teams['away'], match.teams[state],\
                             player.name, i, player.on, player.off, player.yellows, player.reds, player.tries, player.conversion, player.kick, player.penalty])
        pd.DataFrame(rows, columns = ["round", "date", "home_score", "away_score", "home", "away", "team", "player", "position", "on", "off", "yellow", "red", "try", "conversion", "kick", "penalty"]).to_csv(file)


    def _add_match(self, match):
        """
        Insert a new match to this tournament.
        """
        home = match.teams['home']
        away = match.teams['away']
        date = match.date

        match.tournament = self.name
        match.season = self.season
        
        # Check if this match already exists in the tournament
        matches = [matchi for matchi in self.matches if ((matchi.teams['home']==home) & (matchi.teams['away']==away) & (matchi.date==date))]
        for matchi in matches:
            self.matches.remove(matchi)
        matches = [matchi for matchi in self.future if ((matchi.teams['home']==home) & (matchi.teams['away']==away) & (matchi.date==date))]
        for matchi in matches:
            self.future.remove(matchi)
        self.matches.append(match)
        return self
            
    def teams(self):
        """
        Return a set of all of the teams which had matches in this tournament.
        """
        if not hasattr(self, "team_list"):
            teams =  list(set(chain.from_iterable((x.teams['home'], x.teams['away']) for x in self.matches+self.future)))
            if len(teams)>0:
                if isinstance(teams[0], Team):
                    return teams
                else:
                    return [Team(team, {"primary": "#000000"}, team, None) for team in teams]
        else:
            return self.team_list

    def positions(self):
        """
        Provide a list of all of the positions played.
        """
        positions = pd.DataFrame([])
        positions = positions.append([x.lineups['home'].lineup for x in self.matches], ignore_index=True)
        positions = positions.append( [x.lineups['away'].lineup for x in self.matches], ignore_index=True)
        #positions = chain(*positions)
        return positions #list(positions)

    def fixtures_table(self, future=False):
        def _tn(team):
            return team.short_name if hasattr(team, 'short_name') else str(team)

        if not future:
            data = [[pd.to_datetime(match.date), _tn(match.teams['home']), _tn(match.teams['away'])] for match in self.matches]
        else:
            data = [[pd.to_datetime(match.date), _tn(match.teams['home']), _tn(match.teams['away'])] for match in self.future]
        return pd.DataFrame(data, columns=["date", "home", "away"])
    
    def results_table(self):
        def _team_name(team):
            return team.short_name if hasattr(team, 'short_name') else str(team)

        scores = [[_team_name(match.teams['home']), _team_name(match.teams['away']), match.score['home'], match.score['away'],
                   match.score['home']-match.score['away'],
                   match.scores['home'].count("try"),
                   match.scores['away'].count("try")]
                  for match in self.matches if not match.scores==None]
        scores += [[_team_name(match.teams['home']), _team_name(match.teams['away']), match.score['home'], match.score['away'],
                   match.score['home']-match.score['away'],
                    None,
                    None]
                  for match in self.matches if  match.scores==None]
        return pd.DataFrame(scores, columns=["home", "away", "home_score", "away_score", "difference", "home tries", "away tries"])

    def league_table(self):
        df = self.results_table()
        df["Home P"] = 4*(df['home_score']>df['away_score'])
        df["Away P"] = 4*(df['away_score']>df['home_score'])
        df["Home W"] = 1*(df['home_score']>df['away_score'])
        df["Away W"] = 1*(df['away_score']>df['home_score'])
        df["Home L"] = 1*(df['home_score']<df['away_score'])
        df["Away L"] = 1*(df['away_score']<df['home_score'])
        # Draws
        df["Home D"] = 1*(df['home_score']==df['away_score'])
        df["Away D"] = 1*(df['away_score']==df['home_score'])
        # Draw points
        df["Home P"] += 2*(df['away_score']==df['home_score'])
        df["Away P"] += 2*(df['away_score']==df['home_score'])
        # Losing bonus
        df["Away P"] += 1*((df['away_score']<df['home_score']) & ((df['home_score']-df['away_score'])<=7))
        df["Home P"] += 1*((df['home_score']<df['away_score']) & ((df['away_score']-df['home_score'])<=7))
        df["Away B"] = 1*((df['away_score']<df['home_score']) & ((df['home_score']-df['away_score'])<=7))
        df["Home B"] = 1*((df['home_score']<df['away_score']) & ((df['away_score']-df['home_score'])<=7))
        # Try bonus
        df["Away P"] += 1*((df['away tries']>=4))
        df["Away B"] += 1*((df['away tries']>=4))
        df["Home P"] += 1*((df['home tries']>=4))
        df["Home B"] += 1*((df['home tries']>=4))

        points = []
        for team in self.teams():
            points.append({"team": team,
                           "conference": self.team_conferences.get(team.short_name, "A"),
                           "played": df[df.home==team.short_name].count()['Home P'] + df[df.away==team.short_name].count()['Away P'],
                           "won": df[df.home==team.short_name].sum()['Home W'] + df[df.away==team.short_name].sum()['Away W'],
                           "drawn": df[df.home==team.short_name].sum()['Home D'] + df[df.away==team.short_name].sum()['Away D'],
                           "lost": df[df.home==team.short_name].sum()['Home L'] + df[df.away==team.short_name].sum()['Away L'],
                           "for": df[df.home==team.short_name].sum()['home_score'] + df[df.away==team.short_name].sum()['away_score'],
                           "against": df[df.home==team.short_name].sum()['away_score'] + df[df.away==team.short_name].sum()['home_score'],
                           "bonus": df[df.home==team.short_name].sum()['Home B'] + df[df.away==team.short_name].sum()['Away B'],
                           "points": df[df.home==team.short_name].sum()['Home P'] + df[df.away==team.short_name].sum()['Away P']})
        league = pd.DataFrame(points)
        league['diff'] = league['for'] - league['against']
        league = league.sort_values(["conference"])\
                       .sort_values(["points", "diff"], ascending=False)\
                       .reset_index().drop(columns=['index'])

        return league
    
    def lineup_summary(self):
        """
        Produce a full summary of the lineups for this tournament.
        """
        match_data = []
        for match in self.matches:
            if not hasattr(match, "lineups"):
                continue
                #return pd.DataFrame(columns=["name", "team", "home", "away", "game time"])
            data = pd.concat([match.lineups['home'].lineup, match.lineups['away'].lineup])
            teams = pd.DataFrame(np.array([[match.teams['home']] * 23 + [match.teams['away']] * 23]).T, columns=["team"])
            home = pd.DataFrame(np.array([[match.teams['home']] * len(data), [match.teams['away']] * len(data)]).T, columns=["home", "away"])
            home = home.join(teams)
            data = data.reset_index().join(home)
            data['position'] = data.index
            match_data.append(data)
        data = pd.concat(match_data).reset_index()
        return data

    def score_summary(self, squad=False):
        """
        Produce a summary of all the scoring events in this tournament.
        """
        match_data = []
        for match in self.matches:
            if not hasattr(match, "scores") or match.scores==None:
                continue
                #return pd.DataFrame(columns=["name", "team", "home", "away", "value"])
            data = pd.concat([match.scores['home'].scores, match.scores['away'].scores]).reset_index()
            if squad:
                lineups = pd.concat([match.lineups['home'].lineup, match.lineups['away'].lineup]).reset_index()
                data = pd.merge( lineups, data, how='outer',  right_on="player", left_on="name")
            else:
                data = data.rename(columns={"player": "name"})
            teams = pd.DataFrame(np.array([[match.teams['home'].short_name] * len(match.scores['home'].scores) + [match.teams['away'].short_name] * len(match.scores['away'].scores)]).T, columns=["team"])
            home = pd.DataFrame(np.array([[match.teams['home'].short_name] * len(data), [match.teams['away'].short_name] * len(data)]).T, columns=["home", "away"])
            home = home.join(teams)
            if squad:
                data = data.join(home).reset_index().drop(columns=["player", "index_x", "index_y", "index"])
            else:
                data = data.join(home).reset_index().drop(columns=["level_0", "index"])
            match_data.append(data)
        data = pd.concat(match_data).reset_index()
        return data

    def player_score_table(self, team, squad=False):
        """
        Produce a summary of all the player scoring events for this tournament.
        """
        data = self.score_summary(squad=squad)

        players_home = data[(data.team==team) & (data.away==team)].pivot_table(index="name", columns=["home"], values="value", aggfunc="sum")
        players_away = data[(data.team==team) & (data.home==team)].pivot_table(index="name", columns=["away"], values="value", aggfunc="sum")
        player_scores = players_home.join(players_away, how="outer", lsuffix=" [H]", rsuffix=" [A]")
        return player_scores

    def player_time_table(self, team):
        """
        Produce a summary of all the player timing events for this tournament.
        """
        data = self.lineup_summary()
        players_home = data[(data.team==team) & (data.away==team)].pivot_table(index="name", columns=["home"], values="game time", aggfunc="first")
        players_away = data[(data.team==team) & (data.home==team)].pivot_table(index="name", columns=["away"], values="game time", aggfunc="first")
        player_times = players_home.join(players_away, how="outer", lsuffix=" [H]", rsuffix=" [A]")
        return player_times
    
    def scores(self):
        scores = []
        for match in self.matches:
            scores.append(match.all_scores())
        return scores
    
    def players(self):
        positions = self.positions()
        players = set([y['name'] for i,y in positions.iterrows()])
        return list(players)

    def player_covariance(self, team1, team2):
        """
        Get the "covariance matrix" for players in this tournament.
        """
        players1 = team1.squad(self)
        players2 = team2.squad(self)
        matrix_for = np.zeros((len(players1), len(players2)))
        matrix_against = np.zeros((len(players1), len(players2)))
        for match in self.matches:
            if {team1, team2} <= set(match.teams.values()):
                for i, player1 in enumerate(players1):
                    for j, player2 in enumerate(players2):
                        matrix_for[i,j] += player1.onfield_point_mutual_rate(player2, match)[0]
                        matrix_against[i,j] += player1.onfield_point_mutual_rate(player2, match)[1]
        return matrix_for, matrix_against, players1, players2
