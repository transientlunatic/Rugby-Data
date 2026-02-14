"""
Data loading utilities for discovering and loading rugby JSON data files.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from .tournament import Tournament


def find_data_dir() -> Path:
    """Find the data directory, defaulting to json/ relative to the package root."""
    # Try the package root first
    package_root = Path(__file__).parent.parent
    json_dir = package_root / "json"
    if json_dir.exists():
        return json_dir
    # Fall back to current working directory
    cwd_json = Path.cwd() / "json"
    if cwd_json.exists():
        return cwd_json
    return json_dir  # Return expected path even if missing


def find_json_files(data_dir: Path = None, league: str = None,
                    season: str = None) -> List[Path]:
    """
    Discover JSON data files matching optional league/season filters.

    Args:
        data_dir: Base data directory (defaults to json/)
        league: Filter by league name (e.g. 'celtic', 'six-nations')
        season: Filter by season (e.g. '2025-2026')

    Returns:
        List of matching JSON file paths, sorted by name
    """
    if data_dir is None:
        data_dir = find_data_dir()
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists():
        return []

    # Search recursively for JSON files
    all_files = sorted(data_dir.rglob("*.json"))

    results = []
    for f in all_files:
        name = f.stem
        if league and league not in name:
            continue
        if season and season not in name:
            continue
        results.append(f)

    return results


def load_tournament(league: str, season: str,
                    data_dir: Path = None) -> Optional[Tournament]:
    """
    Load a Tournament from a JSON data file.

    Handles both formats:
    - Bare list: list of match dicts (from InCrowdSports API)
    - Dict with metadata: {'matches': [...], 'name': ..., 'season': ...}

    Args:
        league: League name (e.g. 'celtic', 'six-nations')
        season: Season string (e.g. '2025-2026')
        data_dir: Base data directory

    Returns:
        Tournament object or None if file not found
    """
    files = find_json_files(data_dir, league, season)

    if not files:
        return None

    # Use the first match (most specific)
    file_path = files[0]

    with open(file_path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        # Bare list format from API
        matches = pd.DataFrame.from_dict(data)
        return Tournament(league, season, matches)
    elif isinstance(data, dict):
        if 'matches' in data:
            matches = pd.DataFrame.from_dict(data['matches'])
            name = data.get('name', data.get('competition', league))
            season_val = data.get('season', season)
            teams = data.get('teams', None)
            return Tournament(name, season_val, matches, teams)
    return None


def show_data_info(data_dir: Path = None, league: str = None,
                   season: str = None) -> str:
    """
    Display coverage statistics for available data.

    Returns a formatted string with data coverage info.
    """
    files = find_json_files(data_dir, league, season)

    if not files:
        return "No data files found."

    # Group by league
    leagues = {}
    for f in files:
        name = f.stem
        parts = name.rsplit('-', 2)
        if len(parts) >= 3:
            league_name = '-'.join(parts[:-2])
            file_season = f"{parts[-2]}-{parts[-1]}"
        else:
            league_name = name
            file_season = "unknown"

        if league_name not in leagues:
            leagues[league_name] = []
        leagues[league_name].append(file_season)

    lines = []
    lines.append(f"Rugby Data Coverage ({len(files)} files)")
    lines.append("=" * 60)

    for league_name in sorted(leagues.keys()):
        seasons = sorted(leagues[league_name])
        first = seasons[0] if seasons else "?"
        last = seasons[-1] if seasons else "?"
        lines.append(f"  {league_name:<35} {len(seasons):>3} seasons  ({first} - {last})")

    lines.append("")
    lines.append(f"Total: {len(files)} data files across {len(leagues)} competitions")

    return "\n".join(lines)
