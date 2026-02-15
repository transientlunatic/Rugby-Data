"""
Data management CLI commands: update, scrape, scrape-squads, info.
"""

import sys
from datetime import datetime
from pathlib import Path

import click

from ..update import (
    LEAGUE_CONFIGS, SEASON_START_MONTH, MAX_ERRORS_TO_DISPLAY,
    update_league_data
)
from ..data_loader import find_data_dir, show_data_info
from ..scrapers.squads import scrape_squads, get_page_title


@click.group()
def data():
    """Data acquisition and management commands."""
    pass


@data.command()
@click.option('--season', default=None, help='Season to update (e.g., "2024-2025"). Defaults to current season.')
@click.option('--tournaments', '-t', multiple=True,
              type=click.Choice(list(LEAGUE_CONFIGS.keys()) + ['all'], case_sensitive=False),
              default=['urc'],
              help='Which tournaments to update')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without saving')
def update(season, tournaments, dry_run):
    """Update rugby data from various sources."""
    if season is None:
        now = datetime.now()

        # Check if any of the selected tournaments use calendar year
        # (internationals and Southern Hemisphere competitions)
        uses_calendar_year = False
        tournament_list = list(LEAGUE_CONFIGS.keys()) if 'all' in tournaments else tournaments
        for tournament in tournament_list:
            if tournament in LEAGUE_CONFIGS and LEAGUE_CONFIGS[tournament].get('use_calendar_year'):
                uses_calendar_year = True
                break

        # For calendar-year competitions, always use current year
        # For Northern Hemisphere club competitions, use August-based season
        if uses_calendar_year:
            season = f"{now.year}-{now.year + 1}"
        else:
            if now.month >= SEASON_START_MONTH:
                season = f"{now.year}-{now.year + 1}"
            else:
                season = f"{now.year - 1}-{now.year}"

    json_dir = find_data_dir()

    click.echo(f"Updating data for season {season}")
    if dry_run:
        click.echo("DRY RUN - No changes will be saved")
    click.echo()

    total_stats = {'new_matches': 0, 'updated_matches': 0, 'total_matches': 0, 'errors': [], 'warnings': []}

    if 'all' in tournaments:
        tournaments = list(LEAGUE_CONFIGS.keys())

    for tournament in tournaments:
        stats = update_league_data(tournament, season, json_dir, dry_run)
        for key in ['new_matches', 'updated_matches', 'total_matches']:
            total_stats[key] += stats.get(key, 0)
        total_stats['errors'].extend(stats.get('errors', []))
        total_stats['warnings'].extend(stats.get('warnings', []))

    click.echo()
    click.echo("=" * 50)
    click.echo("Summary:")
    click.echo(f"  New matches: {total_stats['new_matches']}")
    click.echo(f"  Updated matches: {total_stats['updated_matches']}")
    click.echo(f"  Total matches: {total_stats['total_matches']}")

    if total_stats['warnings']:
        click.echo(f"  Warnings: {len(total_stats['warnings'])}")
        for warning in total_stats['warnings'][:MAX_ERRORS_TO_DISPLAY]:
            click.echo(f"    - {warning}")
        if len(total_stats['warnings']) > MAX_ERRORS_TO_DISPLAY:
            click.echo(f"    ... and {len(total_stats['warnings']) - MAX_ERRORS_TO_DISPLAY} more")

    if total_stats['errors']:
        click.echo(f"  Errors: {len(total_stats['errors'])}")
        for error in total_stats['errors'][:MAX_ERRORS_TO_DISPLAY]:
            click.echo(f"    - {error}")
        if len(total_stats['errors']) > MAX_ERRORS_TO_DISPLAY:
            click.echo(f"    ... and {len(total_stats['errors']) - MAX_ERRORS_TO_DISPLAY} more")
        sys.exit(1)


@data.command(name='scrape-squads')
@click.option('--year', type=int, required=True, help='Tournament year (e.g., 2026)')
@click.option('--tournament', type=str, required=True,
              help='Tournament name (e.g., "Six Nations Championship", "Rugby World Cup")')
@click.option('--page-title', type=str, default=None,
              help='Custom Wikipedia page title (overrides year/tournament)')
@click.option('--output', '-o', type=str, default=None,
              help='Output file path (default: squads/{year}_{tournament}_squads.{format})')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv']),
              default='json', help='Output format (default: json)')
@click.option('--verbose', '-v', is_flag=True, help='Print verbose output')
def scrape_squads_cmd(year, tournament, page_title, output, output_format, verbose):
    """Scrape squad information from Wikipedia."""
    title = page_title or get_page_title(year, tournament)
    click.echo(f"Scraping squads from: {title}")

    squads = scrape_squads(year, tournament, page_title=page_title)

    if not squads:
        click.echo("No squads found.", err=True)
        sys.exit(1)

    click.echo(f"Found {len(squads)} teams:")
    for team_name, team_data in squads.items():
        coach_info = f" (Coach: {team_data['head_coach']})" if team_data.get('head_coach') else ""
        click.echo(f"  {team_name}: {team_data['squad_size']} players{coach_info}")

    if verbose:
        for team_name, team_data in list(squads.items())[:2]:
            click.echo(f"\n{team_name}:")
            for player in team_data['players'][:5]:
                cap_str = " (c)" if player.get('captain') else ""
                click.echo(f"  - {player['name']}{cap_str} - {player.get('position', '?')}")

    if not output:
        tournament_slug = tournament.replace(' ', '_').lower()
        output = f"squads/{year}_{tournament_slug}_squads.{output_format}"

    from ..scrapers.squads import save_squads
    save_squads(squads, output, output_format)
    click.echo(f"Saved to {output}")


@data.command()
@click.option('--season', '-s', default=None, help='Filter by season')
@click.option('--league', '-l', default=None, help='Filter by league')
def info(season, league):
    """Display data coverage statistics."""
    data_dir = find_data_dir()
    output = show_data_info(data_dir, league, season)
    click.echo(output)
