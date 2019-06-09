import pandas as pd
from itertools import chain

class Player():
    def __init__(self, name):
        self.name = name
    
    def matches(self, tournament):
        return [x for x in tournament.matches if (self in x.home.players) or (self in x.away.players)]
    
    def positions(self, tournament):
        positions = tournament.positions()
        positions = [x for x in tournament.positions() if x.player == self]
        return positions
    
    def scores(self, tournament):
        matches = self.matches(tournament)
        
        scores = []
        scores += [match.home.scores for match in matches]
        scores += [match.away.scores for match in matches]
        scores = chain(*scores)
        return [score for score in scores if score.player.name in self.name]
       
    def _find_position(self, match):
        """
        Find what position this player was playing in for a given match.
        """
        
        position = [position for position in match.home.lineup if position.player == self]
        if len(position)==1:
            side = match.home

        else:
            position = [position for position in match.away.lineup if position.player == self]
            side = match.away
            
        if len(position) == 0: 
            return None, None # This player wasn't playing in this match
        
        return position[0], side
        
    def play_time(self, match):
        position, side = self._find_position(match)
        if position == None: return 0
        return position.play_time()
    
    def total_play_time(self, tournament):
        play_time = sum([self.play_time(x) for x in self.matches(tournament)])
        return play_time
    
    def on_field_points(self, match):
        
        position, side = self._find_position(match)
        
        if position == None: 
            return 0
        
        on_field = sum([score.value for score in side.scores if (score.minute in chain(*position.playing)) 
                    and (score.type is not "conversion")
                   ])
        own_conv = sum([score.value for score in side.scores if (score.player == self) 
                    and (score.type is "conversion")
                   ])
        
        return own_conv + on_field
    
    def total_on_field_points(self, tournament):
        points = sum([self.on_field_points(x) for x in self.matches(tournament)])
        return points

    def __eq__(self, other):
        return self.name == other.name
    
    def __repr__(self):
        return self.name
    
    def __hash__(self):
        return self.name.__hash__()

class Position():
    
    def __init__(self, position, name, on, off, reds, yellows):
        self.player = Player(name)
        self.position = int(position)
        self.on_times = on
        self.off_times = off
        self.cards = {'red': reds, 'yellow': yellows}
        
        self.determine_playing()
        
    def play_time(self):
        return sum([len(time) for time in self.playing])
        
    def determine_playing(self):
        self.playing = []
        if len(self.on_times) > 0:
            if len(self.off_times) < len(self.on_times):
                self.off_times.append(80)
            for i, on_times in enumerate(self.on_times):
                try:
                    self.playing.append(range(self.on_times[i], self.off_times[i]))
                except IndexError:
                    print(self.on_times, self.off_times)
        if len(self.playing)==0: 
            self.playing += range(0)

    def from_dict(self, position, player):
        self.name = player['name']
        self.position = int(position)
        self.on_times = player['on']
        self.off_times = player['off']
        self.cards = {'red': player['reds'], 'yellow': player['yellows']}
        
    def __repr__(self):
        output_string = "{}\t| {}"
        return output_string.format(self.position, self.player.name)

class Score():
    
    def __init__(self, match, player, type, value, minute):
        self.match = match
        self.player = Player(player)
        self.type = type
        self.value = value
        self.minute = minute
        
    def __repr__(self):
        return "{} by {} ({}-{})".format(self.type, self.player.name, self.match.home, self.match.away)

class Team(): 
    
    def __init__(self, name):
        self.name = name.strip()
    
    def __repr__(self):
        return "{}".format(self.name)
    
    def __eq__(self, other):
        return self.name == other.name
    
    def __hash__(self):
        return self.name.__hash__()
    
    def matches(self, tournament, filts=None):
        if filts=="home":
            return [x for x in tournament.matches if (x.home.team == self)]
        elif filts=="away":
            return [x for x in tournament.matches if (x.away.team == self)]
        else:
            return [x for x in tournament.matches if (x.home.team == self) or (x.away.team == self)]
        
    def squad(self, tournament):
        positions = []
        positions += [x.away.lineup for x in self.matches(tournament, filts="away")]
        positions += [x.home.lineup for x in self.matches(tournament, filts="home")]
        positions = chain(*positions)
        players = set([y.player for y in positions])
        return list(players)

class Lineup():
    def __init__(self, match, team, lineup, score, scores):
        self.match = match
        self.team = Team(team)
        self.lineup = self.parse_lineup(lineup)
        self.score = score
        self.scores = [Score(self.match, **score) for score in scores]
        self.players = self.parse_players()
        
    def parse_players(self):
        return [x.player for x in self.lineup]
        
    def parse_lineup(self, lineup):
        return [Position(x[0], **x[1]) for x in lineup.items()]
        
    def __repr__(self):
        return "{}".format(self.team.name)

class Match():
    
    def __init__(self, home, away, stadium, date):
        
        self.home = Lineup(self, **home)
        self.away = Lineup(self, **away)
        
        self.stadium = stadium
        self.date = date
        
    def score(self):
        return [self.home.score, self.away.score]
        
    def __repr__(self):
        return "{}\t({})\tv\t({})\t{}".format(self.home.team.name, self.home.score, self.away.score, self.away.team.name)


class Tournament():
    
    def __init__(self, name, season, matches):
        
        self.matches = [Match(**x[1]) for x in matches.iterrows()]
        
    def teams(self):
        """
        Return a set of all of the teams which had matches in this tournament.
        """
        return list(set(chain.from_iterable((x.home.team, x.away.team) for x in self.matches)))

    def positions(self):
        positions = []
        positions += [x.away.lineup for x in self.matches]
        positions += [x.home.lineup for x in self.matches]
        positions = chain(*positions)
        return list(positions)

    def players(self):
        positions = self.positions()
        players = set([y.player for y in positions])
        return list(players)
