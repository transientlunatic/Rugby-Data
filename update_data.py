#!/usr/bin/env python3
"""
Update rugby data from various sources.

This script fetches updated data for various rugby tournaments and competitions,
focusing only on new or updated matches, and handles future fixtures gracefully.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import List, Dict, Optional
import click


# Configure paths
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR / "json"

# Configure retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# URC API configuration
URC_COMP_ID = 1068
URC_PROVIDER = "rugbyviz"

# Scoring values mapping
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

# Configuration constants
SEASON_START_MONTH = 8  # Rugby season typically starts in August/September
MAX_ERRORS_TO_DISPLAY = 5  # Maximum number of errors to show in summary


def fetch_with_retry(url: str, timeout: int = 30, max_retries: int = MAX_RETRIES) -> Optional[requests.Response]:
    """
    Fetch URL with retry logic.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response object or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                click.echo(f"    Retry {attempt + 1}/{max_retries - 1} after error: {e}", err=True)
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
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
    # Use date and teams as a unique identifier
    date = match.get('date', '')
    home = match.get('home', {}).get('team', '')
    away = match.get('away', {}).get('team', '')
    # Normalize the key to handle minor variations
    return f"{date[:10]}|{home.strip()}|{away.strip()}"


def validate_match_data(match: Dict) -> bool:
    """
    Validate that a match dictionary has required fields.
    
    Args:
        match: Match dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['date', 'home', 'away', 'stadium']
    if not all(field in match for field in required_fields):
        return False
    
    if not isinstance(match.get('home'), dict) or not isinstance(match.get('away'), dict):
        return False
        
    if 'team' not in match['home'] or 'team' not in match['away']:
        return False
        
    return True


def update_urc_data(season: str, dry_run: bool = False) -> Dict:
    """
    Update United Rugby Championship (Celtic League) data.
    
    Args:
        season: Season in format "YYYY-YYYY" (e.g., "2024-2025")
        dry_run: If True, don't save changes
        
    Returns:
        Dict with stats about the update
    """
    click.echo(f"Updating URC data for {season}...")
    
    # Parse season
    start_year = season.split("-")[0]
    
    # API endpoint
    base_url = f"https://rugby-union-feeds.incrowdsports.com/v1/matches?compId={URC_COMP_ID}&season={start_year}01&provider={URC_PROVIDER}"
    
    stats = {
        'new_matches': 0,
        'updated_matches': 0,
        'total_matches': 0,
        'errors': []
    }
    
    try:
        # Fetch data from API
        response = fetch_with_retry(base_url)
        if response is None:
            stats['errors'].append("Failed to fetch URC data after retries")
            return stats
            
        api_data = response.json()
        
        if 'data' not in api_data:
            stats['errors'].append("No 'data' field in API response")
            return stats
            
        # Load existing data
        json_file = JSON_DIR / f"celtic-{season}.json"
        existing_data = load_existing_data(json_file)
        
        # Create lookup for existing matches
        existing_matches = {get_match_key(m): i for i, m in enumerate(existing_data)}
        
        output_data = []
        
        for match in api_data['data']:
            try:
                match_dict = process_urc_match(match, season, start_year)
                
                # Validate match data
                if not validate_match_data(match_dict):
                    stats['errors'].append(f"Invalid match data for {match.get('id')}")
                    continue
                    
                match_key = get_match_key(match_dict)
                
                # Check if this is a new match or update
                if match_key in existing_matches:
                    old_match = existing_data[existing_matches[match_key]]
                    # Check if match has been updated (e.g., results added)
                    old_home_score = old_match.get('home', {}).get('score')
                    old_away_score = old_match.get('away', {}).get('score')
                    new_home_score = match_dict.get('home', {}).get('score')
                    new_away_score = match_dict.get('away', {}).get('score')
                    
                    if (old_home_score is None or old_away_score is None) and \
                       (new_home_score is not None or new_away_score is not None):
                        stats['updated_matches'] += 1
                        click.echo(f"  Updated: {match_dict['home']['team']} v {match_dict['away']['team']}")
                else:
                    stats['new_matches'] += 1
                    click.echo(f"  New: {match_dict['home']['team']} v {match_dict['away']['team']}")
                
                output_data.append(match_dict)
                stats['total_matches'] += 1
                
            except Exception as e:
                stats['errors'].append(f"Error processing match {match.get('id')}: {e}")
                click.echo(f"  Error processing match: {e}", err=True)
                continue
        
        if not dry_run and output_data:
            save_data(json_file, output_data)
            click.echo(f"  Saved {len(output_data)} matches to {json_file.name}")
        
    except requests.RequestException as e:
        stats['errors'].append(f"API request failed: {e}")
        click.echo(f"Error fetching URC data: {e}", err=True)
    except Exception as e:
        stats['errors'].append(f"Unexpected error: {e}")
        click.echo(f"Unexpected error: {e}", err=True)
    
    return stats


def process_urc_match(match: Dict, season: str, start_year: str) -> Dict:
    """Process a single URC match from the API."""
    match_date = datetime.strptime(match['date'], "%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Initialize data structures
    lineup = {"home": {}, "away": {}}
    scores = {"home": [], "away": []}
    player_ids = {}
    position_ids = {}
    
    # Only fetch detailed match data for matches that have likely occurred
    # (not too far in the future)
    if match_date <= datetime.utcnow() + timedelta(days=7):
        try:
            match_url = f"https://rugby-union-feeds.incrowdsports.com/v1/matches/{match['id']}?season={start_year}01&provider={URC_PROVIDER}"
            match_response = fetch_with_retry(match_url)
            
            if match_response and match_response.status_code == 200:
                match_data = match_response.json().get('data', {})
                
                # Process player lineups if available
                if 'players' in match_data.get('homeTeam', {}) and 'players' in match_data.get('awayTeam', {}):
                    # Process home team players
                    for player in match_data['homeTeam']['players']:
                        player_ids[player['id']] = player['name']
                        position_ids[player['id']] = player['positionId']
                        lineup['home'][player['positionId']] = {
                            "name": player['name'],
                            "on": [0] if int(player['positionId']) <= 15 else [],
                            "off": [],
                            "reds": [],
                            "yellows": []
                        }
                    
                    # Process away team players
                    for player in match_data['awayTeam']['players']:
                        player_ids[player['id']] = player['name']
                        position_ids[player['id']] = player['positionId']
                        lineup['away'][player['positionId']] = {
                            "name": player['name'],
                            "on": [0] if int(player['positionId']) <= 15 else [],
                            "off": [],
                            "reds": [],
                            "yellows": []
                        }
                    
                    # Process match events
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
            # If we can't get detailed data, continue with basic match info
            click.echo(f"    Warning: Could not fetch details for match {match.get('id')}: {e}", err=True)
    
    # Determine if the match is completed based on its status
    status = (match.get('status') or "").lower()
    is_completed = status in {"complete", "completed", "finished", "result", "fulltime", "ft", "played"}

    # Build match dictionary
    match_dict = {
        "away": {
            "lineup": lineup['away'],
            "scores": scores['away'],
            "conference": match['awayTeam'].get('group'),
            "score": match['awayTeam'].get('score') if is_completed else None,
            "team": match['awayTeam']['name']
        },
        "home": {
            "lineup": lineup['home'],
            "scores": scores['home'],
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


@click.command()
@click.option('--season', default=None, help='Season to update (e.g., "2024-2025"). Defaults to current season.')
@click.option('--tournaments', '-t', multiple=True, 
              type=click.Choice(['urc', 'all'], case_sensitive=False),
              default=['urc'],
              help='Which tournaments to update')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without saving')
def update(season: Optional[str], tournaments: tuple, dry_run: bool):
    """
    Update rugby data from various sources.
    
    Fetches new and updated match data for specified tournaments.
    """
    # Determine current season if not specified
    if season is None:
        now = datetime.now()
        if now.month >= SEASON_START_MONTH:
            season = f"{now.year}-{now.year + 1}"
        else:
            season = f"{now.year - 1}-{now.year}"
    
    click.echo(f"Updating data for season {season}")
    if dry_run:
        click.echo("DRY RUN - No changes will be saved")
    click.echo()
    
    total_stats = {
        'new_matches': 0,
        'updated_matches': 0,
        'total_matches': 0,
        'errors': []
    }
    
    # Expand 'all' to include all supported tournaments
    if 'all' in tournaments:
        tournaments = ['urc']
    
    # Update each tournament
    for tournament in tournaments:
        if tournament == 'urc':
            stats = update_urc_data(season, dry_run)
            for key in ['new_matches', 'updated_matches', 'total_matches']:
                total_stats[key] += stats.get(key, 0)
            total_stats['errors'].extend(stats.get('errors', []))
    
    # Print summary
    click.echo()
    click.echo("=" * 50)
    click.echo("Summary:")
    click.echo(f"  New matches: {total_stats['new_matches']}")
    click.echo(f"  Updated matches: {total_stats['updated_matches']}")
    click.echo(f"  Total matches: {total_stats['total_matches']}")
    
    if total_stats['errors']:
        click.echo(f"  Errors: {len(total_stats['errors'])}")
        for error in total_stats['errors'][:MAX_ERRORS_TO_DISPLAY]:
            click.echo(f"    - {error}")
        if len(total_stats['errors']) > MAX_ERRORS_TO_DISPLAY:
            click.echo(f"    ... and {len(total_stats['errors']) - MAX_ERRORS_TO_DISPLAY} more")
    
    # Exit with error code if there were errors
    if total_stats['errors']:
        sys.exit(1)


if __name__ == '__main__':
    update()
