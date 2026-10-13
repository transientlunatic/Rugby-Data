"""
Data management CLI commands: update, scrape, scrape-squads, info.
"""

import sys
from datetime import datetime
from pathlib import Path

import click

from ..update import (
    LEAGUE_CONFIGS, MAX_ERRORS_TO_DISPLAY,
    update_league_data, default_season_for_league, seasons_to_update
)
from ..data_loader import find_data_dir, show_data_info
from ..scrapers.squads import scrape_squads, get_page_title
from ..cleanup import clean_directory
from ..enrich import enrich_season, seasons_on_disk
from ..scrapers.espn import ESPN_LEAGUES
from ..team_names import normalise_directory
from ..validation import ERROR, summarise, validate_directory


@click.group()
def data():
    """Data acquisition and management commands."""
    pass


@data.command()
@click.option('--check', is_flag=True, help='Report what would change and exit 1 if anything would; write nothing.')
def normalise(check):
    """Make team names and season filenames canonical in the JSON data.

    See rugby/team_names.py for the name table. Safe to re-run.
    """
    report = normalise_directory(find_data_dir(), check=check)
    if not report:
        click.echo("All team names and filenames are canonical.")
        return
    totals = {}
    for name, info in report.items():
        for old, n in info['teams'].items():
            totals[old] = totals.get(old, 0) + n
        if info['renamed_to']:
            click.echo(f"  rename {name} -> {info['renamed_to']}")
    for old, n in sorted(totals.items(), key=lambda kv: -kv[1]):
        click.echo(f"  {n:6d}  {old!r}")
    click.echo(f"{len(report)} file(s) {'need changes' if check else 'updated'}.")
    if check:
        sys.exit(1)


@data.command(name='enrich-lineups')
@click.option('--tournament', '-t', 'tournaments', multiple=True, required=True,
              type=click.Choice(list(ESPN_LEAGUES.keys())), help='Competition to enrich (repeatable).')
@click.option('--season', default=None, help='One season, e.g. "2024-2025". Default: every season on disk.')
@click.option('--dry-run', is_flag=True, help='Report what would change without writing.')
def enrich_lineups(tournaments, season, dry_run):
    """Add or improve lineups from ESPN.

    ESPN has no substitution minutes, so these lineups record who started and
    who was on the bench only (matches are tagged "lineup_source": "espn").
    A lineup that already has minutes is never replaced.
    """
    json_dir = find_data_dir()
    cache = {}
    for league in tournaments:
        seasons = [season] if season else seasons_on_disk(json_dir, league)
        for s in seasons:
            stats = enrich_season(league, s, json_dir, dry_run, cache)
            if not stats.get('matches') and not stats.get('no_file'):
                continue
            detail = ', '.join(f"{k}={v}" for k, v in sorted(stats.items()) if k != 'matches')
            click.echo(f"{league} {s}: {stats.get('matches', 0)} results; {detail or 'nothing to do'}")


@data.command()
@click.option('--check', is_flag=True, help='Report what would change and exit 1 if anything would; write nothing.')
def clean(check):
    """Drop duplicate matches and mark placeholder 0-0 fixtures as void.

    Void fixtures (0-0, no scorers or lineups: cancelled or never played) get
    null scores and "status": "void". Safe to re-run.
    """
    report = clean_directory(find_data_dir(), check=check)
    for name, c in report.items():
        click.echo(f"  {name}: {c['duplicates']} duplicate(s) removed, {c['void']} marked void")
    if not report:
        click.echo("No duplicates or placeholder results.")
        return
    click.echo(f"{len(report)} file(s) {'need changes' if check else 'updated'}.")
    if check:
        sys.exit(1)


@data.command()
@click.option('--against', default='HEAD', show_default=True,
              help='Git ref to compare with; only matches new or changed since then are checked.')
@click.option('--all', 'every_match', is_flag=True,
              help='Audit every match (report only; historical problems are expected).')
@click.option('--strict', is_flag=True, help='Fail on warnings too.')
def validate(against, every_match, strict):
    """Check matches the last update added or changed for obvious problems.

    Exits 1 on errors (blank/duplicate/non-canonical teams, half results, ...),
    so a scheduled job stops before committing them. Warnings (e.g. 0-0) are
    reported. A markdown summary is written to $GITHUB_STEP_SUMMARY when set.
    """
    import os

    issues = validate_directory(find_data_dir(), against=against, every_match=every_match)
    errors = [i for i in issues if i.severity == ERROR]
    for i in issues:
        click.echo(f"{i.severity.upper():7s} {i.rule:15s} {i.file}: {i.match} -- {i.message}")
    scope = 'every match' if every_match else f"matches new or changed since {against}"
    click.echo(f"{len(errors)} error(s), {len(issues) - len(errors)} warning(s) in {scope}.")
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a') as f:
            f.write("### Data validation\n" + summarise(issues))
    if not every_match and (errors or (strict and issues)):
        sys.exit(1)


@data.command()
@click.option('--season', default=None, help='Season to update (e.g., "2024-2025"). Defaults to current season.')
@click.option('--tournaments', '-t', multiple=True,
              type=click.Choice(list(LEAGUE_CONFIGS.keys()) + ['all'], case_sensitive=False),
              default=['urc'],
              help='Which tournaments to update')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without saving')
def update(season, tournaments, dry_run):
    """Update rugby data from various sources."""
    explicit_season = season
    now = datetime.now()

    json_dir = find_data_dir()

    if explicit_season:
        click.echo(f"Updating data for season {explicit_season}")
    else:
        click.echo("Updating data for the current season (per-league)")
    if dry_run:
        click.echo("DRY RUN - No changes will be saved")
    click.echo()

    total_stats = {'new_matches': 0, 'updated_matches': 0, 'total_matches': 0, 'errors': [], 'warnings': []}

    if 'all' in tournaments:
        tournaments = list(LEAGUE_CONFIGS.keys())

    for tournament in tournaments:
        # Each league's season is computed independently - leagues starting
        # in different months (e.g. Japan League One in December vs European
        # leagues in August) must not share one global "current season".
        config = LEAGUE_CONFIGS[tournament]
        # Besides the current season, also refresh the previous one while it
        # still has finished matches with no result (see seasons_to_update).
        seasons = [explicit_season] if explicit_season else seasons_to_update(
            config, now, json_dir, config['filename_prefix'])
        for season in seasons:
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
