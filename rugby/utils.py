import json

import pandas as pd
from datetime import datetime, date

def determine_type(score):
    """
    Determine the type of score for a pandas Dataframe row.
    """
    if score['try'] > 0: return {'type': 'try', 'value': 5, 'minute': score['try'], 'player': score.player}
    if score['conversion'] > 0: return {'type': 'conversion', 'value': 2, 'minute': score['conversion'], 'player': score.player}
    if score['kick'] > 0: return {'type': 'kick', 'value': 3, 'minute': score['kick'], 'player': score.player}
    if score['penalty'] > 0: return {'type': 'penalty', 'value': 3, 'minute': score['penalty'], 'player': score.player}
    
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))
    
def dense_table_to_nested(data):
    """
    Convert a dense pandas dataframe to a nested, structured data format.
    """
    
    match_list = []
    lineups_table = data.pivot_table(index=["round", "home", "away",  "team"], columns="position", values=["player", "on", "off", "red", "yellow"], aggfunc="first")

    futures = data[pd.isna(data.home_score)].groupby(["round", "date",  "home", "away"])
    for i, match in futures.first().iterrows():
        match_dict = {}
        match_dict['tround'] = i[0]
        match_dict['teams'] = {"home": i[2], "away": i[3]}
        match_dict['home'] = {"team": i[2], "score": float("nan")} 
        match_dict['away'] = {"team": i[3], "score": float("nan")}
        match_dict['date'] = pd.to_datetime(i[1])
        match_dict['stadium'] = ""
        match_list.append(match_dict)
    
    matches = data.groupby(["round", "date",  "home", "away", "home_score", "away_score"])
    for i, match in matches.first().iterrows():
        match_dict = {}
        match_dict['tround'] = i[0]
        match_dict['teams'] = {"home": i[2], "away": i[3]}
        match_dict['home'] = {"team": i[2], "score": i[4]} 
        match_dict['away'] = {"team": i[3], "score": i[5]}
        match_dict['date'] = pd.to_datetime(i[1])
        match_dict['stadium'] = ""

        if not (int(i[0]), i[2], i[3]) in lineups_table.index:
            match_list.append(match_dict)
        else:
            for j, team in lineups_table.loc[(int(i[0]), i[2], i[3])].iterrows():

                lineups = {}

                lineup = pd.DataFrame(team.player).join(pd.DataFrame(team.on), rsuffix="_on").join(pd.DataFrame(team.off), rsuffix="_off").join(pd.DataFrame(team.red), rsuffix="_red").join(pd.DataFrame(team.yellow), rsuffix="_yellow")
                lineup.columns=["name", "on", "off", "reds", "yellows"]
                lineup.index = lineup.index.astype(int)
                if j == i[2]:
                    match_dict['home']['lineup'] = lineup.T.to_dict()
                else:
                    match_dict['away']['lineup'] = lineup.T.to_dict()

            scores = {}
            for team in match_dict['teams'].values():
                events = data[(data.home==i[2]) & (data.away==i[3]) & (data.team==team)]
                score_events = events[events[["try", "penalty", "conversion", "kick"]].sum(axis=1) > 0]
                team_scores = []
                for j, score in score_events.iterrows():
                    team_scores.append(determine_type(score))
                if team == i[2]:
                    match_dict['home']['scores'] = team_scores
                else:
                    match_dict['away']['scores'] = team_scores

            match_list.append(match_dict)

    return pd.DataFrame(match_list)



def add_metadata(filename, **metadata):
    """
    Add metadata to a tournament JSON file.
    """
    output = {}
    with open(filename, "r") as f:
        data = json.load(f)
    if not "matches" in data.keys():
        output['matches'] = [match for match in data]
    else:
        output = data
    for key, value in metadata.items():
        output[key] = value
        
    with open(filename, "w") as f:
        json.dump(output, f, default=json_serial)


def intersections(a,b):
    ranges = []
    i = j = 0
    while i < len(a) and j < len(b):
        a_left, a_right = a[i]
        b_left, b_right = b[j]

        if a_right < b_right:
            i += 1
        else:
            j += 1

        if a_right >= b_left and b_right >= a_left:
            end_pts = sorted([a_left, a_right, b_left, b_right])
            middle = [end_pts[1], end_pts[2]]
            ranges.append(middle)

    ri = 0
    while ri < len(ranges)-1:
        if ranges[ri][1] == ranges[ri+1][0]:
            ranges[ri:ri+2] = [[ranges[ri][0], ranges[ri+1][1]]]

        ri += 1
    return ranges

def total_time_from_ranges(subs):
    total_time = 0
    time = []
    for i in range(int(len(subs)/2)):
            time.append([subs[i], subs[i+1]])
            total_time += (subs[i+1] - subs[i])
    return time, total_time
