"""
Plotting CLI commands: heatmap, player-matrix.
"""

import sys
from pathlib import Path

import click

from ..data_loader import load_tournament


@click.group()
def plot():
    """Generate rugby data visualisations."""
    pass


@plot.command()
@click.argument('league')
@click.argument('season')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path (default: display interactively)')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def heatmap(league, season, output, data_dir):
    """Generate a results heatmap for a competition.

    Examples:
        rugby plot heatmap celtic 2025-2026
        rugby plot heatmap six-nations 2025-2026 -o six_nations.png
    """
    import matplotlib.pyplot as plt
    from .. import plotting

    plt.style.use(plotting.style)

    tournament = load_tournament(league, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {league} {season}", err=True)
        sys.exit(1)

    try:
        results_df = tournament.results_table()
        fig = plotting.league_heatmap(results_df, league, season)

        if output:
            fig.savefig(output, bbox_inches='tight')
            click.echo(f"Saved heatmap to {output}")
        else:
            plt.show()
    except Exception as e:
        click.echo(f"Error generating heatmap: {e}", err=True)
        sys.exit(1)


@plot.command(name='player-matrix')
@click.argument('league')
@click.argument('season')
@click.argument('team')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
@click.option('--type', 'plot_type', type=click.Choice(['time', 'score']),
              default='time', help='Plot type: time or score matrix')
def player_matrix(league, season, team, output, data_dir, plot_type):
    """Generate a player time/score matrix for a team.

    Examples:
        rugby plot player-matrix celtic 2025-2026 "Leinster Rugby"
        rugby plot player-matrix six-nations 2025-2026 Scotland -o scotland.png
    """
    import matplotlib.pyplot as plt
    from .. import plotting

    plt.style.use(plotting.style)

    tournament = load_tournament(league, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {league} {season}", err=True)
        sys.exit(1)

    try:
        fig, ax = plt.subplots(1, 1, figsize=(8, 12), dpi=300)
        labelfont = {"fontsize": 5}

        if plot_type == 'time':
            plotting.player_time_matrix_plot(tournament, team, ax=ax, labelfont=labelfont)
        else:
            plotting.player_score_matrix_plot(tournament, team, ax=ax, labelfont=labelfont)

        fig.tight_layout()

        if output:
            fig.savefig(output, bbox_inches='tight')
            click.echo(f"Saved player matrix to {output}")
        else:
            plt.show()
    except Exception as e:
        click.echo(f"Error generating player matrix: {e}", err=True)
        sys.exit(1)
