import requests
import bs4
from bs4 import BeautifulSoup
import dateparser
import yaml
import pandas
import json

import rugby
import rugby.data

from datetime import date, datetime

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def process_game_page(url, season = None, season_range=[8,7]):
    
    if season:
        years = season.split("-")
        years = [int(year.strip()) for year in years]
    
    match = {}
    
    r2 = requests.get(url)
    soup = BeautifulSoup(r2.text, 'html.parser')
    body = soup.find("body")
    matchhead = body.find("div", {"class": "match-head"})
    
    details = matchhead.find_all("li")
    date_temp = dateparser.parse(f"{details[1].text}")
    if date_temp.month < season_range[0]:
        # Must be in the second year of the season
        year=years[1]
    else:
        year=years[0]
    # Need to manually modify the date as there's no year in the string
    match['date'] = dateparser.parse(f"{details[1].text} {year}")
    
    match['stadium'] = details[2].text.split("\n")[0].strip()    
    match['home'] = {}
    match['away'] = {}
    teamdetails = matchhead.find("div", {"class":"match-head__fixture"}).find_all("div", {"class": "match-head__fixture-side"})
    match['home']['team'] = teamdetails[0].find("a", {"class":"match-head__team-name"}).find("span", {"class": "swap-text__target"}).text
    try:
        match['home']['score'] = int(teamdetails[0].find("span", {"class": "match-head__score"}).text)
        match['home']['scores'] = process_team_details(teamdetails[0])
        match['away']['score'] = int(teamdetails[1].find("span", {"class": "match-head__score"}).text)
        match['away']['scores'] = process_team_details(teamdetails[1])
    except:
        pass
    
    match['away']['team'] = teamdetails[1].find("a", {"class":"match-head__team-name"}).find("span", {"class": "swap-text__target"}).text
    
    

    # Parse the line-ups
    try:
        teamslineup = body.find_all("ul", {"class": "team-lineups__list-group"})
        if len(teamslineup)<4:
            return match
        lineups = {}
        for i, lineup in enumerate(['home', 'away']):
            lineups[lineup] = {}
            players = teamslineup[2*i].find_all("li")
            for player in players:
                try:
                    number = int(player.find("span", {"class": "team-lineups__list-player-number"}).text.strip())

                    name = player.find("span", {"class": "team-lineups__list-player-name"}).text.strip()


                    offs = []
                    ons = []
                    yellows = []
                    reds = []
                    events = player.find_all("span", {"class": "team-lineups__list-events"})
                    for event in events:
                        img = event.find("img")
                        if img:
                            if (img.get("src").split("/")[-1]) == "substitution_off.svg":
                                offs.append(int(event.text.strip().split("'")[0]))
                            elif (img.get("src").split("/")[-1]) == "substitution_on.svg":
                                ons.append(int(event.text.strip().split("'")[0]))
                            elif (img.get("src").split("/")[-1]) == "yellow_card.svg":
                                yellows.append(int(event.text.strip().split("'")[0]))
                            elif (img.get("src").split("/")[-1]) == "red_card.svg":
                                reds.append(int(event.text.strip().split("'")[0]))
                            else:
                                print("Unknown event type: {}".format(img.get("src").split("/")[-1]))
                    if number <= 15:
                        ons.append(0)
                    lineups[lineup][number] = {"name":name, "on": ons, "off": offs, "reds": reds, "yellows": yellows}
                except:
                    continue
        match['home']['lineup'] = lineups['home']
        match['away']['lineup'] = lineups['away']
    except:
        pass
    return match



def process_team_details(teamdetails):
    

    for e in teamdetails.findAll('br'):
        e.extract()


    scores = teamdetails.find("p", {"class":"match-head__scorers"})
    types={"Tries:":"try", "Penalties:":"penalty", "Conversions:": "conversion", "Drop-Goals:": "drop goal"}
    values={"Tries:":5, "Penalties:":3, "Conversions:": 2, "Drop-Goals:": 3}
    scoresdic = []
    current = ""
    for score in scores.children:
        if (isinstance(score, bs4.element.Tag)) : 
            if (score.text.strip())=="": continue
            current = types[score.text]
            value = values[score.text]
        elif not current == "":
            insert = score.strip().split(",")
            cplayer = ""
            for ins in insert:
                ins = ins.split("\xa0")
                if len(ins)==1: ins = [cplayer, ins[0].strip(")")]
                else:
                    ins[0] = ins[0].strip()
                    ins[1] = ins[1].strip("(")
                    ins[1] = ins[1].strip(")")
                    cplayer = ins[0]
                for minute in ins[1].split(","):
                    minute = minute.strip("(")
                    if minute=="": continue
                    scoresdic.append(
                        {
                         "type": current, "player": ins[0], 
                         "value": value, "minute": int(minute)})
    return scoresdic

def get_match_list(league, season, base = "http://www.skysports.com/rugby-union/competitions", use_recent=False):
    """
    Attempts to fetch a list of URLs for matches in a given season, and return them as a list.
    """
    
    league = "-".join(league.split())
    
    if not use_recent:
        season = season.split("-")
        season = "-".join([season[0], season[1][2:]])
    else:
        season=""
    
    url = "{}/{}/results/{}".format(base, league.lower(), season)
    print(url)
    
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')

    links = soup.find_all("a", {"class":"matches__item matches__link"})
    # matches__item matches__link
    urls = []
    for link in links:
        year = link.find_previous("h3", {"class": "fixres__header1"}).text.strip().split()[1]
        date = link.find_previous("h4", {"class": "fixres__header2"}).text.strip()
        date = dateparser.parse(f"{year} {date}")
        url = link.get("href").split("/")
        url.insert(-1, "teams")
        url = "/".join(url)
        urls.append(url)
    return urls

def download_json(season, league, 
                  base = "http://www.skysports.com/rugby-union/competitions", season_range=[8,7],
                  use_recent=False,
                 ):
    urls = get_match_list(league=league, season=season, use_recent=use_recent)
    
    try:
        games = pandas.read_json(rugby.__path__[0]+"/json/{}-{}.json".format(league, season), dtype=object)
        
        matches = [rugby.data.Match(row) for index, row in games.iterrows()]
        match_urls = [match.url for match in matches]

    except:
        match_urls = []
        games = pandas.DataFrame()

    number = 0
    for url in urls:
        if url in match_urls: 
            game = None
        else:
            number += 1
            game = process_game_page(url, season=season, season_range=season_range)
        
            game['url'] = url
        if game:
            games = games.append(game, ignore_index=True)
    print(f"Downloaded {number} new results")
    with open(rugby.__path__[0]+"/json_data/{}-{}.json".format(league, season), 'w') as f:
        json.dump(games.to_dict(), f, default=json_serial)


def get_fixture_list(league, season, base = "http://www.skysports.com/rugby-union/competitions"):
    """
    Attempts to fetch a list of URLs for matches in a given season, and return them as a list.
    """
    
    league = "-".join(league.split())
    
    season = season.split("-")
    season = "-".join([season[0], season[1][2:]])
    
    url = "{}/{}/fixtures".format(base, league.lower())
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')

    links = soup.find_all("a", {"class":"matches__item matches__link"})
    # matches__item matches__link
    urls = []
    for link in links:
        year = link.find_previous("h3", {"class": "fixres__header1"}).text.strip().split()[1]
        date = link.find_previous("h4", {"class": "fixres__header2"}).text.strip()
        date = dateparser.parse(f"{year} {date}")
        url = link.get("href").split("/")
        url.insert(-1, "teams")
        url = "/".join(url)
        urls.append(url)
    return urls

def download_fixtures(season, league, 
                  base = "http://www.skysports.com/rugby-union/competitions", season_range=[8,7]):
    urls = get_fixture_list(league=league, season=season)
    
    try:
        games = pandas.read_json(rugby.__path__[0]+"/json-data/{}-fixtures.json".format(league), dtype=object)
    
        #matches = [rugby.data.Match(row) for index, row in data.iterrows()]
        match_urls = [game.url for i, game in games.iterrows()]

    except:
        match_urls = []
        games = pandas.DataFrame()
    number = 0
    for url in urls:
        if url in match_urls: 
            game = None
        else:
        
            game = process_game_page(url, season=season, season_range=season_range)
        
            game['url'] = url
        if game:
            number += 1
            games = games.append(game, ignore_index=True)
    print(f"Downloaded {number} new fixtures")
    with open(rugby.__path__[0]+"/json_data/{}-fixtures.json".format(league), 'w') as f:
        json.dump(games.T.to_dict(), f, default=json_serial)
