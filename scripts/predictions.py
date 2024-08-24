import aesara.tensor as at
import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm
import seaborn as sns
import datetime
import otter

from matplotlib.ticker import StrMethodFormatter

from rugby import *

team_maps = {
    #"TBC": "TBC",
    
    "Zebre Parma": "Zebre",
    "Zebre": "Zebre",
    
    "Leinster": "Leinster",
    "Leinster Rugby": "Leinster",
    
    "Ulster": "Ulster",
    "Ulster Rugby": "Ulster",
    
    "Scarlets": "Scarlets",
    
    "Connacht": "Connacht",
    "Connacht Rugby": "Connacht",
    
    "Edinburgh": "Edinburgh",
    "Edinburgh Rugby": "Edinburgh",
    
    "Dragons": "Dragons",
    "Dragons RFC": "Dragons",
    
    "Benetton": "Benetton",
    "Benetton Rugby": "Benetton",
    
    "Ospreys": "Ospreys",
    
    "Munster": "Munster",
    "Munster Rugby": "Munster",
    
    "Cardiff Blues": "Cardiff",
    "Cardiff Rugby": "Cardiff",
    
    "Glasgow Warriors": "Glasgow",
    "Glasgow": "Glasgow",
    
    "Vodacom Bulls": "Bulls",
    "Blue Bulls": "Bulls",
    "Vodacom Bulls": "Bulls",
    "Bulls": "Bulls",
    
    "DHL Stormers": "Stormers",
    "Stormers": "Stormers",
    
    "Emirates Lions": "Lions",
    "Lions": "Lions",
    
    "Cell C Sharks": "Sharks",
    "Hollywoodbets Sharks": "Sharks",
    "Sharks": "Sharks"
}

report = otter.Otter("index.html")

data = pd.read_json("json/celtic-2023-2024.json")
data_2 = pd.read_json("json/celtic-2024-2025.json")

pro14 = Tournament("URC", "2023-2024", data)
pro14_2 = Tournament("Pro 14", "2024-2025", data_2)
pro14.matches = pro14.matches + pro14_2.matches
data_2 = pd.read_json("json/celtic-2022-2023.json")
pro14_2 = Tournament("Pro 14", "2022-2023", data_2)
pro14.matches = pro14.matches + pro14_2.matches


matches = [m for m in pro14.matches if (m.home.team.name != "TBC") and (m.away.team.name != "TBC")]
pro14.matches = matches

def factorise_teams(data):
    mappings = dict(zip(set(team_maps.values()), range(len(set(team_maps.values())))))
    print(mappings)
    return [mappings[d] for d in data], list(mappings.keys())

##### Train the model

home_idx, teams = factorise_teams([team_maps[match.home.team.name] for match in pro14.matches if (match.date.date() < datetime.date.today())])
away_idx, _ = factorise_teams([team_maps[match.away.team.name] for match in pro14.matches if (match.date.date() < datetime.date.today())])
#
coords = {"team": teams}

with pm.Model(coords=coords) as model:
    # constant data
    home_team = pm.Data("home_team", home_idx, dims="match")
    away_team = pm.Data("away_team", away_idx, dims="match")

    # global model parameters
    home = pm.Normal("home", mu=0, sigma=1)
    sd_att = pm.HalfNormal("sd_att", sigma=2)
    sd_def = pm.HalfNormal("sd_def", sigma=2)
    intercept = pm.Normal("intercept", mu=3, sigma=1)

    # team-specific model parameters
    atts_star = pm.Normal("atts_star", mu=0, sigma=sd_att, dims="team")
    defs_star = pm.Normal("defs_star", mu=0, sigma=sd_def, dims="team")

    atts = pm.Deterministic("atts", atts_star - at.mean(atts_star), dims="team")
    defs = pm.Deterministic("defs", defs_star - at.mean(defs_star), dims="team")
    home_theta = at.exp(intercept + home + atts[home_idx] + defs[away_idx])
    away_theta = at.exp(intercept + atts[away_idx] + defs[home_idx])

    # likelihood of observed data
    home_points = pm.Poisson(
        "home_points",
        mu=home_theta,
        observed=[match.home.score for match in pro14.matches if match.date.date() < datetime.date.today()],
        dims=("match"),
    )
    away_points = pm.Poisson(
        "away_points",
        mu=away_theta,
        observed=[match.away.score for match in pro14.matches if match.date.date() < datetime.date.today()],
        dims=("match"),
    )
    trace = pm.sample(2000, tune=10000, cores=4)
trace_hdi = az.hdi(trace)

with report:
    report += "# Attack diagnostics"
    
    f, ax = plt.subplots(figsize=(12, 6), dpi=300)

    ax.scatter(coords["team"], trace.posterior["atts"].median(dim=("chain", "draw")), color="C0", alpha=1, s=100)
    ax.vlines(
        teams,
        trace_hdi["atts"].sel({"hdi": "lower"}),
        trace_hdi["atts"].sel({"hdi": "higher"}),
        alpha=0.6,
        lw=5,
        color="C0",
    )
    ax.set_xlabel("Teams")
    ax.set_ylabel("Posterior Attack Strength")
    ax.set_title("HDI of Team-wise Attack Strength");

    report + f

with report:

    report += "# Defence diagnostics"

    f, ax = plt.subplots(figsize=(12, 6), dpi=300)

    ax.scatter(coords["team"], trace.posterior["defs"].median(dim=("chain", "draw")), color="C0", alpha=1, s=100)
    ax.vlines(
        teams,
        trace_hdi["defs"].sel({"hdi": "lower"}),
        trace_hdi["defs"].sel({"hdi": "higher"}),
        alpha=0.6,
        lw=5,
        color="C0",
    )
    ax.set_xlabel("Teams")
    ax.set_ylabel("Posterior Defence Strength")
    ax.set_title("HDI of Team-wise Defence Strength");

    report + f

##### Make predictions

with model:
    home_idx, teams = factorise_teams([team_maps[match.home.team.name] for match in pro14.matches if match.date.date() >= datetime.date.today()])
    away_idx, _ = factorise_teams([team_maps[match.away.team.name] for match in pro14.matches if match.date.date() >= datetime.date.today()])
    coords = {"team": teams}
    pm.set_data({"home_team": home_idx,
                "away_team": away_idx
                }, coords=coords)
    predictions = pm.sample_posterior_predictive(trace, extend_inferencedata=False, predictions=True)

pp = predictions.predictions

upcoming_matches = [match for match in pro14.matches if match.date.date() > datetime.date.today()]

for i, match in enumerate(upcoming_matches):
    with report:
        scores = np.hstack(pp.home_points[:,:,i]) - np.hstack(pp.away_points[:,:,i])
        line = f"{match.home} ({(np.sum(scores > 0)/len(scores)):.1%}) v ({(np.sum(scores < 0)/len(scores)):.1%}) {match.away}"
        report + line
        
