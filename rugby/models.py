from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound

from sqlalchemy import or_

from datetime import datetime, timedelta

Base = declarative_base()

import rugby
from flask import url_for

import os
if 'RUGBYDB' in os.environ:
    db = os.environ['RUGBYDB']
else:
    db = f"{rugby.__path__[0]}/rugby.db"

import bcrypt

engine = create_engine("sqlite:///"+db)

Base.metadata.create_all(engine)

# from sqlalchemy.orm import sessionmaker
# DBSession = sessionmaker(bind=engine)
# session = DBSession()

from flask_sqlalchemy_session import current_session as session

import rugby.data

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    username = Column(String(250), nullable=False)
    password = Column(String(250), nullable=False)
    registered_on = Column(DateTime, nullable=False)
    admin = Column(Boolean, nullable=False, default=False)

    @classmethod
    def find_user(cls, username, session=session):
        """Find a user from a username."""
        return session.query(cls).filter_by(username=username).one()

    @classmethod
    def create_user(cls, name, username, password, session=session):
        """Create a new user in the database."""
        try:
            user = cls.find_user(username, session)
        except NoResultFound:
            salt = bcrypt.gensalt()
            user = cls(name=name,
                       username=username,
                       password=bcrypt.hashpw(password.encode(), salt),
                       registered_on=datetime.now())
            session.add(user)
            session.commit()
        return user

    @classmethod
    def login(cls, username, password):
        """Log the user in."""
        db_user = cls.find_user(username)
        salt = bcrypt.gensalt()
        if bcrypt.checkpw(password.encode(), db_user.password):
            return {"id": db_user.username}
        else:
            return False

class Tournament(Base):
    __tablename__ = 'tournament'
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)

    def to_dict(self):
        return {"name": self.name}

    @classmethod
    def update(cls, name, data, session=session):
        tournament = Tournament.from_query(name, session)
        if 'name' in data:
            tournament.name = data['name']
        session.commit()
        return tournament
    
    @classmethod
    def all(cls, session=session):
        return session.query(cls).all()
    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None
        
    @classmethod
    def from_query(self, name, session=session):
        tournament = session.query(Tournament).filter_by(name=name).one()
        return tournament

    @classmethod
    def remove(cls, name, session=session):
        tournaments = session.query(Tournament).filter_by(name=name).all()
        for tournament in tournaments:
            session.delete(tournament)
        session.commit()
        return {}
    
    @classmethod
    def add(self, tournament,  session=session):
        try:
            if isinstance(tournament, rugby.data.Tournament):
                tournament = session.query(Tournament).filter_by(name=tournament.name).one()
            else:
                tournament = session.query(Tournament).filter_by(name=tournament['name']).one()
        except NoResultFound:
            tournament = Tournament(name=tournament['name'])
            session.add(tournament)
            session.commit()
        return tournament

class Season(Base):
    __tablename__ = "season"
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    tournament = Column(Integer, ForeignKey("tournament.id"))

    def to_dict(self):
        return {"name": self.name,
                "tournament": Tournament.get(self.tournament).to_dict()
        }
    
    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None
    
    @classmethod
    def all(cls, session=session):
        return session.query(cls).all()
    
    @classmethod
    def add(self, tournament, session=session):
        tournament_id = Tournament.add(tournament).id
        try:
            if isinstance(tournament, rugby.data.Tournament):
                season = session.query(Season).filter_by(name=tournament.season, tournament=tournament_id).one()
            else:
                season = session.query(Season).filter_by(name=tournament['season'], tournament=tournament_id).one()
        except NoResultFound:
            season = Season(name=tournament['season'], tournament=tournament_id)
            session.add(season)
            session.commit()
        return season
    
    @classmethod
    def from_query(self, tournament, season=None, session=session):
        tournament = session.query(Tournament).filter_by(name=tournament).one()

        if season:
            season = session.query(Season).filter_by(name=season, tournament=tournament.id).one()

            conferences = ConferenceMap.for_season(season)
            
            tournament = rugby.data.Tournament(
                name=tournament.name,
                season=season.name, 
                matches=season.matches(session))
            tournament.season_id = season.id
            
            tournament.team_conferences = conferences

            
            
            return tournament
        else:
            seasons = session.query(Season).filter_by(tournament=tournament.id).all()
            return [rugby.data.Tournament(
                name=tournament.name,
                season=season.name, 
                matches=season.matches(session)) for season in seasons]
        
    
    def matches(self, session=session):
        matches = session.query(Match).filter_by(season=self.id).all()
        matches = [match.to_dict(session) for match in matches]
        return matches

class ConferenceMap(Base):
    __tablename__ = "conference_map"
    id = Column(Integer, primary_key=True)
    season = Column(Integer, ForeignKey("season.id"))
    team = Column(Integer, ForeignKey("team.id"))
    conference = Column(String(255), nullable=False)

    @classmethod
    def for_season(cls, season):
        print("for_season", season)
        teams = session.query(cls).filter_by(season=season.id).all()
        mapping = {}
        mapping = {Team.get(team.team).shortname : team.conference for team in teams}
        return mapping

    @classmethod
    def add(cls, tournament, season, mapping):
        """
        Add a dictionary of teams and conferences to the model.
        """
        tournament_id = session.query(Tournament).filter_by(name=tournament).one().id
        season_id = session.query(Season).filter_by(name=season, tournament=tournament_id).one().id
        for team, conference in mapping.items():
            team_id = session.query(Team).filter_by(shortname=team).one().id
            mapping = cls(season=season_id, team=team_id, conference=conference)
            session.add(mapping)
        session.commit()
            
        
    
class Team(Base):
    __tablename__ = "team"
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    shortname = Column(String(250), nullable=False)
    color_primary = Column(String(6), nullable=False)
    color_secondary = Column(String(6), nullable=False)
    color_extra = Column(String(6), nullable=False)
    country = Column(String(250), nullable=False)

    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None
    
    @classmethod
    def all(self):
        return session.query(Team).all()
    
    @classmethod
    def from_query(cls, shortname, session=session):
        return session.query(cls).filter_by(shortname=shortname).one()

    @classmethod
    def remove(cls, shortname, session=session):
        team = Team.from_query(shortname)
        session.delete(team)
        session.commit()
    
    @classmethod
    def update(cls, shortname, data, session=session):
        team = Team.from_query(shortname)
        if 'name' in data:
            team.name = str(data['name']).replace("/", "-").strip()
        if 'shortname' in data:
            team.shortname = str(data['shortname']).replace("/", "~").strip()
        if 'color_primary' in data:
            team.color_primary = str(data['color_primary']).strip("#").strip()
        if 'color_secondary' in data:
            team.color_secondary = str(data['color_secondary']).strip("#").strip()
        session.commit()
        return team
    
    @classmethod
    def add(cls, data, session=session):
        """
        Add a team to the database if it doesn't exist already.
        Return its ID.
        """
        try:
            if isinstance(data, rugby.data.Team):
                team = Team.from_query(data.short_name)
            else:
                team = Team.from_query(shortname=data['short_name'])
        except NoResultFound:
            print("C")
            team = cls(name=data['name'],
                        shortname=data['short_name'],
                        color_primary=data['color_primary'],
                        color_secondary=data['color_secondary'],
                        color_extra=data['color_extra'],
                        country=data['country']
            )
            session.add(team)
            session.commit()
        return team
    
    def to_dict(self):
        return dict(name=self.name, 
                    short_name=self.shortname,
                    colors={"primary": self.color_primary,
                            "secondary": self.color_secondary,
                            "extra": self.color_extra},
                    country=self.country                    
                   )
    
class Match(Base):
    __tablename__ = "match"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    season = Column(Integer, ForeignKey("season.id"))
    home = Column(Integer, ForeignKey("team.id"))
    away = Column(Integer, ForeignKey("team.id"))
    home_score = Column(Integer)
    away_score = Column(Integer)

    @classmethod
    def all(self):
        return [rugby.data.Match(match.to_dict(session)).to_rest()
                for match in session.query(Match).all()]

    @classmethod
    def remove(cls, home, away, date, session=session):
        date = datetime.strptime(date, "%Y-%m-%d")
        home = Team.from_query(home, session).id
        away = Team.from_query(away, session).id
        match = session.query(Match).filter(
            Match.date.between(date, date+timedelta(days=1))).filter_by(home=home, away=away).one()

        session.delete(match)
        session.commit()
        
    @classmethod
    def update(cls, home, away, date, data, session=session):
        date = datetime.strptime(date, "%Y-%m-%d")
        home = Team.from_query(home, session).id
        away = Team.from_query(away, session).id
        match = session.query(Match).filter(
            Match.date.between(date, date+timedelta(days=1))).filter_by(home=home, away=away).one()
        
        if 'date' in data:
            match.date = datetime.strptime(data['date'], "%Y-%m-%d")
        if ('season' in data) and ('tournament' in data):
            season = Season.from_query(season=data['season'],
                                             tournament=data['tournament'],
                                             session=session).season_id
            print(season)
            match.season = int(season)
        if 'home_team' in data:
            match.home = Team.from_query(data['home_team'], session).id
        if 'away_team' in data:
            match.away = Team.from_query(data['away_team'], session).id
        if 'home_score' in data:
            match.home_score = float(data['home_score'])
        if 'away_score' in data:
            match.away_score = float(data['away_score'])
        session.commit()
        return rugby.data.Match(match.to_dict(session))

    
    @classmethod
    def from_query(self, home, away, date=None, limit=30, session=session):
        
        home = Team.from_query(home, session).id
        away = Team.from_query(away, session).id

        if date:
            date = datetime.strptime(date, "%Y-%m-%d")
        
            match = session.query(Match).filter(Match.date.between(date, date+timedelta(days=1))).filter_by(home=home, away=away).one()
            match_o = rugby.data.Match(match.to_dict(session))
            match_o.id = match.id
            return match_o
            

        else:
            matches = session.query(Match).filter(
                (Match.home.in_([home, away]) & (Match.away.in_([home, away])))).order_by(Match.date.desc()).limit(limit)
            return [rugby.data.Match(match.to_dict(session)).to_rest() for match in matches]

    @classmethod
    def add_dict(self, match):
        """
        Add a match object to the database.
        """
        tournament = session.query(Tournament).filter_by(name=match['tournament']).one()
        season = session.query(Season).filter_by(tournament=tournament.id, name=match['season']).one()
        home = Team.from_query(match['home_team'])
        away = Team.from_query(match['away_team'])

        try:
            match = session.query(Match).filter_by(date=match['date'], home=home.id, away=away.id, season=season.id).one()
        except NoResultFound:

            date=datetime.strptime(match['date'], "%Y-%m-%d")
            
            match = Match(date=date,
                 season=season.id,
                  home=home.id,
                  away=away.id,
                  home_score = match['home_score'],
                          away_score = match['away_score'],
                 )
            session.add(match)
            session.commit()
        return match
    
    @classmethod
    def add(self, match):
        """
        Add a match object to the database.
        """
        tournament = session.query(Tournament).filter_by(name=match.tournament).one()
        season = session.query(Season).filter_by(tournament=tournament.id, name=match.season).one()
        home = Team.from_query(match.teams['home'].short_name)
        away = Team.from_query(match.teams['away'].short_name)

        try:
            match = session.query(Match).filter_by(date=match.date, home=home.id, away=away.id, season=season.id).one()
        except NoResultFound:
            match = Match(date=match.date,
                 season=season.id,
                  home=home.id,
                  away=away.id,
                  home_score = match.score['home'],
                          away_score = match.score['away'],
                 )
            session.add(match)
            session.commit()
        return match
    
    def to_dict(self, session=session):
        season = Season.get(self.season)
        tournament = Tournament.get(season.tournament)
        home = rugby.data.Team(**session.query(Team).filter_by(id=self.home).one().to_dict())
        away = rugby.data.Team(**session.query(Team).filter_by(id=self.away).one().to_dict())
        if self.home_score:
            home=dict(score=self.home_score, team=home.to_dict())
            away=dict(score=self.away_score, team=away.to_dict())
        else:
            home=dict(team=home.to_dict(), score=float('nan'))
            away=dict(team=away.to_dict(), score=float('nan'))
        return dict(date=self.date, 
                    season=season.name,
                    tournament=tournament.name,
                    stadium=None,
                    home=home, 
                    away=away)


class Player(Base):
    __tablename__ = 'player'
    id = Column(Integer, primary_key=True)
    firstname = Column(String(250), nullable=False)
    surname = Column(String(250), nullable=False)
    country = Column(String(250), nullable=True)
    @classmethod
    def all(cls, session=session):
        return session.query(cls).all()
    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None

    @property
    def name(self):
        return f"{self.firstname} {self.surname}"
        
    @property
    def to_dict(self):
        return {"name": f"{self.firstname} {self.surname}",
                "firstname": self.firstname,
                "surname": self.surname,
                "country": self.country}
        
    @property
    def name(self):
        return f"{self.firstname} {self.surname}"
        
    @classmethod
    def from_query(cls, firstname, surname, session=session):
        return session.query(cls).filter_by(firstname=firstname, surname=surname).one()
    
    @classmethod
    def add(self, firstname, surname, country=None,  session=session):
        try:
            player = session.query(Player).filter_by(firstname=firstname, surname=surname).one()
        except NoResultFound:
            player = Player(firstname=firstname, surname=surname, country=country)
            session.add(player)
            session.commit()
        return player

class Position(Base):
    __tablename__ = 'position'
    id = Column(Integer, primary_key=True)
    match = Column(Integer, ForeignKey("match.id"))
    team = Column(Integer, ForeignKey("team.id"))
    player = Column(Integer, ForeignKey("player.id"), nullable=False)
    number = Column(Integer)
    on = Column(String(250))
    off = Column(String(250))
    reds = Column(String(250))
    yellows = Column(String(250))

    @classmethod
    def from_query(cls, home, away, date, session=session):
        home = Team.from_query(home.replace("_", " "), session).id
        away = Team.from_query(away.replace("_", " "), session).id
        date = datetime.strptime(date, "%Y-%m-%d")
        
        match = session.query(Match).filter(Match.date.between(date, date+timedelta(days=1))).filter_by(home=home, away=away).one()
        positions = session.query(cls).filter_by(match=match.id).all()

        out = []
        for position in positions:
            try:
                on = position.on.split(",")
                if on[0] != '':
                    on = list(map(float, on))
                else:
                    on = None
            except:
                on = position.on

            try:
                off = position.off.split(",")
                if off[0] != '':
                    off = list(map(float, off))
                elif on != None:
                    off = [80]
                else:
                    off = None
            except:
                if on:
                    off = [80]
                else:
                    off = position.off
            print(on, off)
            try:
                time_ranges = sorted(on + off)
            except:
                time_ranges = []
                
            out.append({
                "number": position.number,
                "player": Player.get(position.player),
                "on": on,
                "off": off,
                "time_ranges": time_ranges,
                "team": position.team
                })
        
        return out
    
    @classmethod
    def all(cls, session=session):
        return session.query(cls).all()
    
    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None
    
    @classmethod
    def add(cls, match, player, team, number, on, off, reds, yellows, session=session):
        firstname = player.split()[0]
        surname = " ".join(player.split()[1:])
        player = Player.from_query(firstname=firstname, surname=surname, session=session)
        team = Team.from_query(shortname=team, session=session)
        try:
            position = session.query(cls).filter_by(match=match, team=team.id, player=player.id, number=number).one()
        except NoResultFound:
            position = cls(match=match, team=team.id, player=player.id, number=number, on=on, off=off, reds=reds, yellows=yellows)
            session.add(position)
            session.commit()
        return position

class EventType(Base):
    __tablename__ = "event_type"
    id = Column(Integer, primary_key=True)
    name = Column(String(250), unique=True)
    score = Column(Integer, nullable=True)
    
    @classmethod
    def get(cls, id):
        try:
            return session.query(cls).filter_by(id=id).one()
        except NoResultFound:
            return None
        
    @classmethod
    def add(cls, name, score=None,  session=session):
        try:
            event_type = session.query(cls).filter_by(name=name).one()
        except NoResultFound:
            event_type = EventType(name=name, score=score)
            session.add(event_type)
            session.commit()
        return event_type

    @classmethod
    def from_query(cls, name, session=session):
        return session.query(cls).filter_by(name=name).one()
    
class Event(Base):
    __tablename__ = "event"
    id = Column(Integer, primary_key=True)
    type = Column(Integer, ForeignKey("event_type.id"))
    time = Column(Integer, nullable=True)
    team = Column(Integer, ForeignKey("team.id"))
    match = Column(Integer, ForeignKey("match.id"))
    player = Column(Integer, ForeignKey("player.id"), nullable=True)
    score = Column(Integer, nullable=True)

    @classmethod
    def get(cls, idn, session=session):
        try:
            idn = int(idn)
            print(type(idn))
            return session.query(cls).filter_by(id=idn).one()
        except NoResultFound:
            return None
    
    def to_rest(self):
        event_data = {"type": EventType.get(self.type).name,
                      "team": Team.get(self.team).shortname,
                      "time": self.time}
        if self.player:
           event_data["player"] = Player.get(self.player).name
        if self.score:
            event_data["score"] = self.score
        event_data['id'] = self.id
        return event_data
    
    @classmethod
    def add(cls, home, away, date, team, event_type, time=None, player=None,  score=None,  session=session):
        match = Match.from_query(home=home, away=away, date=date)
        team = Team.from_query(shortname=team)
        event_type = EventType.from_query(name=event_type)
        if player:
            player = Player.from_query(surname=player.split(" ")[1], firstname=player.split(" ")[0])
            player_id=player.id
        else:
            player_id=None
        try:
            if not player:
                event = session.query(cls).filter_by(match=match.id, time=time, team=team.id, type=event_type.id).one()
            else:
                event = session.query(cls).filter_by(match=match.id, time=time, team=team.id, type=event_type.id, player=player.id).one()
        except NoResultFound:
            event = cls(type=event_type.id, time=time, team=team.id, match=match.id, player=player_id, score=score)
            session.add(event)
            session.commit()
        return event

    @classmethod
    def add_dict(cls, data, session=session):
        all_data = dict(
            time = None,
            player = None,
            score = None,
            )
        all_data.update(data)
        return cls.add(session=session, **data)
        
    
    @classmethod
    def from_query(cls, session=session, **kwargs):
        if {"home", "away", "date"} <= set(kwargs.keys()):
            match = Match.from_query(home=kwargs['home'], away=kwargs['away'], date=kwargs['date'])
            events = session.query(cls).filter_by(match=match.id).all()
        else:
            return {}
        out = []
        for event in events:
            out.append(event.to_rest())
        return out

    @classmethod
    def update(cls, idnumber, data, session=session):
        event = Event.get(idnumber, session)
        team = Team.from_query(shortname=data['team'])
        event_type = EventType.from_query(name=data['type'])
        
        event.type = event_type.id
        event.team = Team.from_query(shortname=data['team']).id
        event.time = data['time']
        # if self.player:
        #    event_data["player"] = Player.from_query(self.player).id
        if data['score']:
            event.score = data['score']
        session.commit()
        return event
