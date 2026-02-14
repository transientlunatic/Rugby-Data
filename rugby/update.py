"""
Core data update logic for fetching rugby data from various sources.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import click
import requests

from .scrapers.six_nations import scrape_championship


# Configure retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# League/Competition Configuration
LEAGUE_CONFIGS = {
    'urc': {
        'comp_id': 1068,
        'provider': 'rugbyviz',
        'name': 'United Rugby Championship',
        'filename_prefix': 'celtic',
        'wikipedia_fallback': True,
        'api_cutoff_year': 2005  # API data available from 2005-2006 onwards
    },
    'premiership': {
        'comp_id': 1011,
        'provider': 'rugbyviz',
        'name': 'Gallagher Premiership',
        'filename_prefix': 'premiership'
    },
    'top14': {
        'comp_id': 1002,
        'provider': 'rugbyviz',
        'name': 'Top 14',
        'filename_prefix': 'top14'
    },
    'pro-d2': {
        'comp_id': 1013,
        'provider': 'rugbyviz',
        'name': 'Pro D2',
        'filename_prefix': 'pro-d2'
    },
    'euro-champions': {
        'comp_id': 1008,
        'provider': 'rugbyviz',
        'name': 'European Rugby Champions Cup',
        'filename_prefix': 'euro-champions'
    },
    'euro-challenge': {
        'comp_id': 1026,
        'provider': 'rugbyviz',
        'name': 'European Rugby Challenge Cup',
        'filename_prefix': 'euro-challenge'
    },
    'championship': {
        'comp_id': 1051,
        'provider': 'rugbyviz',
        'name': 'RFU Championship',
        'filename_prefix': 'championship',
        'wikipedia_fallback': True,  # Use Wikipedia for older seasons
        'api_cutoff_year': 2024  # API data available from 2024-2025 onwards
    },
    'six-nations': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Six Nations Championship',
        'filename_prefix': 'six-nations'
    },
    'mid-year-internationals': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Mid-year Internationals',
        'filename_prefix': 'mid-year-internationals'
    },
    'end-of-year-internationals': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'End-of-year Internationals',
        'filename_prefix': 'end-of-year-internationals'
    },
    'world-cup': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Rugby World Cup',
        'filename_prefix': 'rugby-world-cup',
        'use_year_only': True  # Use just year, not season
    },
    'super-rugby': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Super Rugby',
        'filename_prefix': 'super-rugby'
    },
    'japan-league-one': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Japan Rugby League One',
        'filename_prefix': 'japan-league-one'
    },
    'currie-cup': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'Currie Cup',
        'filename_prefix': 'currie-cup'
    },
    'npc': {
        'comp_id': None,
        'provider': 'wikipedia',
        'name': 'National Provincial Championship',
        'filename_prefix': 'npc'
    },
}

SCORING_VALUES = {
    "Try": 5,
    "Penalty Try": 5,
    "Penalty": 3,
    "Conversion": 2,
    "Drop goal": 3,
    "Missed drop goal": 0,
    "Missed penalty": 0,
    "Missed conversion": 0
}

SEASON_START_MONTH = 8
MAX_ERRORS_TO_DISPLAY = 5

# World Cup years (every 4 years since 1987)
WORLD_CUP_YEARS = [1987, 1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023, 2027, 2031, 2035]


def is_world_cup_year(year: int) -> bool:
    """Check if a given year is a Rugby World Cup year."""
    return year in WORLD_CUP_YEARS or (year >= 1987 and (year - 1987) % 4 == 0)


def fetch_with_retry(url: str, timeout: int = 30, max_retries: int = MAX_RETRIES) -> Optional[requests.Response]:
    """Fetch URL with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                click.echo(f"    Retry {attempt + 1}/{max_retries - 1} after error: {e}", err=True)
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                click.echo(f"    Failed after {max_retries} attempts: {e}", err=True)
                return None
    return None


def load_existing_data(filepath: Path) -> List[Dict]:
    """Load existing JSON data if it exists."""
    if filepath.exists():
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            click.echo(f"Warning: Could not load {filepath}: {e}", err=True)
            return []
    return []


def save_data(filepath: Path, data: List[Dict]):
    """Save data to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def get_match_key(match: Dict) -> str:
    """Generate a unique key for a match."""
    date = match.get('date', '')
    home = match.get('home', {}).get('team', '')
    away = match.get('away', {}).get('team', '')
    return f"{date[:10]}|{home.strip()}|{away.strip()}"


def validate_match_data(match: Dict) -> bool:
    """Validate that a match dictionary has required fields."""
    # Stadium is optional - not all matches have venue information
    required_fields = ['date', 'home', 'away']
    if not all(field in match for field in required_fields):
        return False
    if not isinstance(match.get('home'), dict) or not isinstance(match.get('away'), dict):
        return False
    if 'team' not in match['home'] or 'team' not in match['away']:
        return False
    return True


def process_match(match: Dict, season: str, start_year: str, league_config: Dict) -> Dict:
    """Process a single match from the API."""
    match_date = datetime.strptime(match['date'], "%Y-%m-%dT%H:%M:%S.%fZ")

    lineup = {"home": {}, "away": {}}
    scores = {"home": [], "away": []}
    player_ids = {}
    position_ids = {}

    if match_date <= datetime.utcnow() + timedelta(days=7):
        try:
            match_url = f"https://rugby-union-feeds.incrowdsports.com/v1/matches/{match['id']}?season={start_year}01&provider={league_config['provider']}"
            match_response = fetch_with_retry(match_url)

            if match_response and match_response.status_code == 200:
                match_data = match_response.json().get('data', {})

                if 'players' in match_data.get('homeTeam', {}) and 'players' in match_data.get('awayTeam', {}):
                    for player in match_data['homeTeam']['players']:
                        player_ids[player['id']] = player['name']
                        position_ids[player['id']] = player['positionId']
                        lineup['home'][player['positionId']] = {
                            "name": player['name'],
                            "on": [0] if int(player['positionId']) <= 15 else [],
                            "off": [], "reds": [], "yellows": []
                        }

                    for player in match_data['awayTeam']['players']:
                        player_ids[player['id']] = player['name']
                        position_ids[player['id']] = player['positionId']
                        lineup['away'][player['positionId']] = {
                            "name": player['name'],
                            "on": [0] if int(player['positionId']) <= 15 else [],
                            "off": [], "reds": [], "yellows": []
                        }

                    home_id = match_data['homeTeam']['id']
                    away_id = match_data['awayTeam']['id']

                    for event in match_data.get('events', []):
                        if 'teamId' not in event:
                            continue
                        team = "home" if event['teamId'] == home_id else "away"

                        if event['type'] in SCORING_VALUES:
                            player = player_ids.get(event.get('playerId'), None)
                            scores[team].append({
                                'minute': event.get('minute', 0),
                                'type': event['type'],
                                'player': player,
                                'value': SCORING_VALUES[event['type']]
                            })
                        elif event['type'] == "Sub On" and 'playerId' in event:
                            player_pos = position_ids.get(event['playerId'])
                            if player_pos in lineup[team]:
                                lineup[team][player_pos]['on'].append(event.get('minute', 0))
                        elif event['type'] == "Sub Off" and 'playerId' in event:
                            player_pos = position_ids.get(event['playerId'])
                            if player_pos in lineup[team]:
                                lineup[team][player_pos]['off'].append(event.get('minute', 0))
                        elif event['type'] == "Yellow card" and 'playerId' in event:
                            player_pos = position_ids.get(event['playerId'])
                            if player_pos in lineup[team]:
                                lineup[team][player_pos]['yellows'].append(event.get('minute', 0))
                        elif event['type'] == "Red card" and 'playerId' in event:
                            player_pos = position_ids.get(event['playerId'])
                            if player_pos in lineup[team]:
                                lineup[team][player_pos]['reds'].append(event.get('minute', 0))
        except Exception as e:
            click.echo(f"    Warning: Could not fetch details for match {match.get('id')}: {e}", err=True)

    status = (match.get('status') or "").lower()
    is_completed = status in {"complete", "completed", "finished", "result", "fulltime", "ft", "played"}

    match_dict = {
        "away": {
            "lineup": lineup['away'], "scores": scores['away'],
            "conference": match['awayTeam'].get('group'),
            "score": match['awayTeam'].get('score') if is_completed else None,
            "team": match['awayTeam']['name']
        },
        "home": {
            "lineup": lineup['home'], "scores": scores['home'],
            "conference": match['homeTeam'].get('group'),
            "score": match['homeTeam'].get('score') if is_completed else None,
            "team": match['homeTeam']['name']
        },
        "round": match.get('round', 0),
        "round_type": "league" if match.get('roundTypeId') == 1 else "knockout",
        "stadium": match['venue']['name'],
        "date": match['date'],
        "attendance": match.get('attendance')
    }

    if "officials" in match:
        match_dict["officials"] = match['officials']

    return match_dict


def update_wikipedia_data(league: str, season: str, league_config: Dict,
                          json_dir: Path, dry_run: bool = False) -> Dict:
    """Update data for competitions that use Wikipedia as the source."""
    stats = {'new_matches': 0, 'updated_matches': 0, 'total_matches': 0, 'errors': []}

    try:
        start_year = int(season.split("-")[0])

        # For World Cup, check if this is a World Cup year
        if league_config.get('use_year_only') and league_config['name'] == 'Rugby World Cup':
            if not is_world_cup_year(start_year):
                click.echo(f"  Skipping {start_year} - not a World Cup year (World Cups occur in: {', '.join(map(str, [y for y in WORLD_CUP_YEARS if abs(y - start_year) <= 8]))})")
                return stats

        click.echo(f"  Fetching from Wikipedia for year {start_year}...")
        scraped_matches = scrape_championship(start_year, league_config['name'])

        if not scraped_matches:
            stats['errors'].append(f"No matches found on Wikipedia for {start_year}")
            return stats

        click.echo(f"  Retrieved {len(scraped_matches)} matches from Wikipedia")

        # Determine filename - use year only for World Cup, season for others
        if league_config.get('use_year_only'):
            json_file = json_dir / f"{league_config['filename_prefix']}-{start_year}.json"
        else:
            json_file = json_dir / f"{league_config['filename_prefix']}-{season}.json"
        existing_data = load_existing_data(json_file)
        existing_matches = {get_match_key(m): i for i, m in enumerate(existing_data)}

        output_data = []
        for match in scraped_matches:
            try:
                if not validate_match_data(match):
                    stats['errors'].append(f"Invalid match data: {match.get('home', {}).get('team')} v {match.get('away', {}).get('team')}")
                    continue

                match_key = get_match_key(match)
                if match_key in existing_matches:
                    old_match = existing_data[existing_matches[match_key]]
                    old_home_score = old_match.get('home', {}).get('score')
                    new_home_score = match.get('home', {}).get('score')
                    if old_home_score is None and new_home_score is not None:
                        stats['updated_matches'] += 1
                        click.echo(f"  Updated: {match['home']['team']} v {match['away']['team']}")
                else:
                    stats['new_matches'] += 1
                    click.echo(f"  New: {match['home']['team']} v {match['away']['team']}")

                output_data.append(match)
                stats['total_matches'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing match: {e}")
                continue

        if not dry_run and output_data:
            save_data(json_file, output_data)
            click.echo(f"  Saved {len(output_data)} matches to {json_file.name}")

    except Exception as e:
        stats['errors'].append(f"Wikipedia scraping failed: {e}")
        click.echo(f"Error scraping Wikipedia for {league_config['name']}: {e}", err=True)

    return stats


def update_league_data(league: str, season: str, json_dir: Path,
                       dry_run: bool = False) -> Dict:
    """Update data for a specific rugby league/competition."""
    if league not in LEAGUE_CONFIGS:
        return {
            'new_matches': 0, 'updated_matches': 0, 'total_matches': 0,
            'errors': [f"Unknown league: {league}. Available: {', '.join(LEAGUE_CONFIGS.keys())}"]
        }

    league_config = LEAGUE_CONFIGS[league]
    click.echo(f"Updating {league_config['name']} data for {season}...")

    # Check if this is a Wikipedia-only source
    if league_config['provider'] == 'wikipedia':
        return update_wikipedia_data(league, season, league_config, json_dir, dry_run)

    # Check if we should use Wikipedia fallback for older seasons
    start_year = int(season.split("-")[0])
    if league_config.get('wikipedia_fallback'):
        api_cutoff = league_config.get('api_cutoff_year', 2100)  # Default to far future
        if start_year < api_cutoff:
            click.echo(f"  Using Wikipedia for {season} (API data available from {api_cutoff}-{api_cutoff+1} onwards)")
            return update_wikipedia_data(league, season, league_config, json_dir, dry_run)

    start_year = season.split("-")[0]
    base_url = f"https://rugby-union-feeds.incrowdsports.com/v1/matches?compId={league_config['comp_id']}&season={start_year}01&provider={league_config['provider']}"

    stats = {'new_matches': 0, 'updated_matches': 0, 'total_matches': 0, 'errors': []}

    try:
        response = fetch_with_retry(base_url)
        if response is None:
            stats['errors'].append(f"Failed to fetch {league_config['name']} data after retries")
            return stats

        api_data = response.json()
        if 'data' not in api_data:
            stats['errors'].append("No 'data' field in API response")
            return stats

        json_file = json_dir / f"{league_config['filename_prefix']}-{season}.json"
        existing_data = load_existing_data(json_file)
        existing_matches = {get_match_key(m): i for i, m in enumerate(existing_data)}

        output_data = []
        for match in api_data['data']:
            try:
                match_dict = process_match(match, season, start_year, league_config)
                if not validate_match_data(match_dict):
                    stats['errors'].append(f"Invalid match data for {match.get('id')}")
                    continue

                match_key = get_match_key(match_dict)
                if match_key in existing_matches:
                    old_match = existing_data[existing_matches[match_key]]
                    old_home_score = old_match.get('home', {}).get('score')
                    new_home_score = match_dict.get('home', {}).get('score')
                    if old_home_score is None and new_home_score is not None:
                        stats['updated_matches'] += 1
                        click.echo(f"  Updated: {match_dict['home']['team']} v {match_dict['away']['team']}")
                else:
                    stats['new_matches'] += 1
                    click.echo(f"  New: {match_dict['home']['team']} v {match_dict['away']['team']}")

                output_data.append(match_dict)
                stats['total_matches'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing match {match.get('id')}: {e}")
                continue

        if not dry_run and output_data:
            save_data(json_file, output_data)
            click.echo(f"  Saved {len(output_data)} matches to {json_file.name}")

    except requests.RequestException as e:
        stats['errors'].append(f"API request failed: {e}")
    except Exception as e:
        stats['errors'].append(f"Unexpected error: {e}")

    return stats
