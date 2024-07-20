import click
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta, date
import json

@click.group()
def scrape():
    pass

@click.option("--year", "year", default=None)
@click.option("--round", "tournament_round", default=1)
@click.argument("season")
@scrape.command(name="united")
def united_rugby(season, year, tournament_round):
    tournament = "celtic"
    click.echo("Scraping URC data")
    if not year: year=season
    base_url = f"https://rugby-union-feeds.incrowdsports.com/v1/matches?compId=1068&season={season[:4]}01&provider=rugbyviz"
    output_data = []# {"matches": [], "tournament": tournament, "season": season}
    r = requests.get(base_url)

    if r.status_code == 200:
        data = r.json()
        i = 0
        for match in data['data']:
            # click.echo(f"{match['homeTeam']['name']} v {match['awayTeam']['name']}")
            tround = match['round']
            tround_type = "league" if match['roundTypeId'] == 1 else "knockout"
            #click.echo(f"Round {tround} {tround_type}")
            date = datetime.strptime(match['date'], "%Y-%m-%dT%H:%M:%S.%fZ")
            #click.echo(f"\t{date}")
            lineup = {"home": {}, "away": {}}
            scores = {"home": [], "away": []}

            player_ids = {}
            position_ids = {}
            
            if not date > (date.today() + timedelta(days=7)):
                match_page = f"https://rugby-union-feeds.incrowdsports.com/v1/matches/{match['id']}?season={season[:4]}01&provider=rugbyviz"
                match_r = requests.get(match_page)
                if match_r.status_code == 200:
                    data = match_r.json()['data']
                    if "players" in data['homeTeam'] and "players" in data['awayTeam']:
                        for player_1, player_2 in zip(data['homeTeam']['players'], data['awayTeam']['players']):
                            player_ids[player_1['id']] = player_1['name']
                            position_ids[player_1['id']] = player_1['positionId']
                            lineup['home'][player_1['positionId']] = {"name": player_1['name'],
                                                                      "on": [], "off": [], "reds": [], "yellows": []}
                            if int(player_1['positionId']) <= 15:
                                lineup['home'][player_1['positionId']]['on'].append(0)

                            player_ids[player_2['id']] = player_2['name']
                            position_ids[player_2['id']] = player_2['positionId']
                            lineup['away'][player_2['positionId']] = {"name": player_2['name'],
                                                                      "on": [], "off": [], "reds": [], "yellows": []}
                            if int(player_2['positionId']) <= 15:
                                lineup['away'][player_2['positionId']]['on'].append(0)
                    else:
                        click.echo(f"{match['homeTeam']['name']} v {match['awayTeam']['name']}")
                        print(data)
                    # Get scoring events and substitutions
                    home_id = data['homeTeam']['id']
                    away_id = data['awayTeam']['id']      

                    # print(home_id, away_id)

                    try_mins = []
                    for event in data['events']:
                        scoring = {"Try": 5,
                                  "Penalty Try": 5,
                                  "Penalty": 2,
                                  "Conversion": 2,
                                  "Missed drop goal": 0,
                                  "Missed penalty": 0,
                                  "Missed conversion": 0,
                                  "Drop goal": 2}
                        subs = {"Sub On": "on", "Sub Off":"off"}
                        cards = {"Yellow card": "yellows",
                                 "Red card": "reds"}
                        if 'teamId' in event:
                            team = "home" if event['teamId'] == home_id else "away"
                            if event['type'] in scoring:
                                player = player_ids[event['playerId']] if "playerId" in event else 0
                                scores[team].append({'minute': event['minute'],
                                                     'type': event['type'],
                                                     'player': player,
                                                     'value': scoring[event['type']]})
                            elif event['type'] in subs:
                                lineup[team][position_ids[event['playerId']]][subs[event['type']]].append(event['minute'])
                            elif event['type'] in cards:
                                lineup[team][position_ids[event['playerId']]][cards[event['type']]].append(event['minute'])
                            else:
                                print(event['type'])
                                break

            match_id = match['id']

            match_dict = {"away": {"lineup": lineup['away'],
                                   "scores": scores['away'],
                                   "conference": match['awayTeam']['group'],
                                   "score": match['awayTeam']['score'] if match['status'] else None,
                                   "team": match['awayTeam']['name']},
                          "home": {"lineup": lineup['home'],
                                   "scores": scores['home'],
                                   "conference": match['homeTeam']['group'],
                                   "score": match['homeTeam']['score'] if match['status']  else None,
                                   "team": match['homeTeam']['name']},
                          "round": tround,
                          "round_type": tround_type,
                          "stadium": match['venue']['name'],
                          "date": match['date'],
                          "attendance": match['attendance'],
                          }

            if "officials" in match:
                match_dict["officials"] = match['officials']

            output_data.append(match_dict)
        with open(f"{tournament}-{season}.json", "w") as f:
            json.dump(output_data, f)
            
if __name__ == "__main__":
    scrape()
