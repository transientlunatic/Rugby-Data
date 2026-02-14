"""
Rugby analysis CLI commands: squad-analysis, tournament-predict, league-table, results, player-stats.
"""

import sys
import json
from pathlib import Path

import click
import pandas as pd

from ..data_loader import find_data_dir, load_tournament


# Position to section mapping for squad analysis
POSITION_SECTIONS = {
    'Hooker': 'forwards',
    'Prop': 'forwards',
    'Lock': 'forwards',
    'Back Row': 'mixed',
    'Scrum-half': 'backs',
    'Fly-half': 'backs',
    'Centre': 'backs',
    'Wing': 'backs',
    'Fullback': 'backs',
}


def check_rugby_ranking_available():
    """Check if rugby-ranking package is available."""
    try:
        from rugby_ranking.model.squad_analysis import SquadAnalyzer
        return True
    except ImportError as e:
        click.echo(f"Warning: rugby-ranking package not available: {e}", err=True)
        return False


@click.group()
def analysis():
    """Rugby analysis commands."""
    pass


@analysis.command(name='league-table')
@click.argument('league')
@click.argument('season')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def league_table(league, season, data_dir):
    """Display the league table for a competition.

    Examples:
        rugby analysis league-table celtic 2025-2026
        rugby analysis league-table premiership 2025-2026
    """
    tournament = load_tournament(league, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {league} {season}", err=True)
        sys.exit(1)

    try:
        table = tournament.league_table()
        click.echo(f"\n{league.upper()} {season} - League Table\n")
        click.echo(table.to_string(index=False))
    except Exception as e:
        click.echo(f"Error generating league table: {e}", err=True)
        sys.exit(1)


@analysis.command()
@click.argument('league')
@click.argument('season')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def results(league, season, data_dir):
    """Display match results for a competition.

    Examples:
        rugby analysis results celtic 2025-2026
        rugby analysis results six-nations 2025-2026
    """
    tournament = load_tournament(league, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {league} {season}", err=True)
        sys.exit(1)

    try:
        results_df = tournament.results_table()
        click.echo(f"\n{league.upper()} {season} - Results\n")
        click.echo(results_df.to_string(index=False))
    except Exception as e:
        click.echo(f"Error generating results: {e}", err=True)
        sys.exit(1)


@analysis.command(name='player-stats')
@click.argument('player')
@click.option('--league', '-l', default=None, help='Filter by league')
@click.option('--season', '-s', default=None, help='Filter by season')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def player_stats(player, league, season, data_dir):
    """Display statistics for a player.

    Examples:
        rugby analysis player-stats "Finn Russell" -l six-nations -s 2025-2026
    """
    if not league or not season:
        click.echo("Both --league and --season are required for player-stats.", err=True)
        sys.exit(1)

    tournament = load_tournament(league, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {league} {season}", err=True)
        sys.exit(1)

    try:
        lineup_data = tournament.lineup_summary()
        player_data = lineup_data[lineup_data['name'].str.contains(player, case=False, na=False)]

        if player_data.empty:
            click.echo(f"No data found for player '{player}' in {league} {season}", err=True)
            sys.exit(1)

        click.echo(f"\nPlayer Stats: {player}")
        click.echo(f"Competition: {league} {season}\n")

        total_time = player_data['game time'].sum()
        matches_played = len(player_data)
        click.echo(f"Matches played: {matches_played}")
        click.echo(f"Total game time: {total_time:.0f} minutes")
        click.echo(f"Average game time: {total_time/matches_played:.0f} minutes per match")

        click.echo(f"\nMatch details:")
        for _, row in player_data.iterrows():
            click.echo(f"  {row.get('home', '?')} v {row.get('away', '?')}: {row['game time']:.0f} min")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@analysis.command(name='squad-analysis')
@click.option('--squad-file', '-f', type=click.Path(exists=True),
              help='Path to squad CSV or JSON file')
@click.option('--team', '-t', help='Team name')
@click.option('--season', '-s', default='2025-2026', help='Season (default: 2025-2026)')
@click.option('--model-path', '-m', type=click.Path(),
              help='Path to trained model checkpoint')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file for results')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
def squad_analysis(squad_file, team, season, model_path, output, output_format):
    """Analyze squad depth and strength (requires rugby-ranking)."""
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for squad analysis.", err=True)
        sys.exit(1)

    from rugby_ranking.model.squad_analysis import SquadAnalyzer
    from rugby_ranking.model.core import RugbyModel, ModelConfig
    from rugby_ranking.model.data import MatchDataset
    import arviz as az

    squad_df = None

    if not squad_file:
        if not team:
            click.echo("Error: Either --squad-file or --team must be provided.", err=True)
            sys.exit(1)

        json_candidates = [
            f'squads/{season.split("-")[0]}_six_nations_championship_squads.json',
            f'squads/six_nations_{season}.json',
        ]

        for json_file in json_candidates:
            if Path(json_file).exists():
                try:
                    with open(json_file) as f:
                        squads = json.load(f)
                    if team in squads:
                        squad_df = pd.DataFrame(squads[team]['players'])
                        squad_file = json_file
                        break
                except Exception as e:
                    click.echo(f"Warning: Error reading {json_file}: {e}", err=True)

        if squad_df is None:
            team_slug = team.lower().replace(' ', '_')
            squad_file = f'squads/{team_slug}_{season}.csv'
            if not Path(squad_file).exists():
                click.echo(f"Error: Squad file not found for {team}", err=True)
                sys.exit(1)

    if not team and squad_file:
        team = Path(squad_file).stem.replace(f'_{season}', '').replace('_', ' ').title()

    click.echo(f"Analyzing squad for {team} ({season})...")

    if squad_df is None:
        if squad_file.endswith('.json'):
            with open(squad_file) as f:
                squads = json.load(f)
            if team in squads:
                squad_df = pd.DataFrame(squads[team]['players'])
            else:
                click.echo(f"Error: Team {team} not found in {squad_file}", err=True)
                sys.exit(1)
        else:
            squad_df = pd.read_csv(squad_file)

    if 'name' in squad_df.columns and 'player' not in squad_df.columns:
        squad_df = pd.DataFrame({
            'player': squad_df['name'],
            'position_text': squad_df['position'],
            'club': squad_df.get('club', 'Unknown'),
            'team': team,
            'season': season,
            'section': squad_df['position'].map(POSITION_SECTIONS).fillna('mixed'),
            'primary_position': squad_df['position'],
            'secondary_positions': '[]'
        })

    click.echo(f"Loaded {len(squad_df)} players")

    if not model_path:
        model_path = Path.home() / '.cache/rugby_ranking/international-mini5/trace.nc'
    else:
        model_path = Path(model_path)

    if not model_path.exists():
        click.echo(f"\nError: Model checkpoint not found: {model_path}", err=True)
        sys.exit(1)

    click.echo("Loading model...")
    trace = az.from_netcdf(model_path)

    try:
        dataset = MatchDataset.empty()
        model = RugbyModel()
        analyzer = SquadAnalyzer(model, trace)
    except Exception as e:
        click.echo(f"Error initializing model: {e}", err=True)
        sys.exit(1)

    analysis_result = analyzer.analyze_squad(squad_df, team, season)

    if output_format == 'json' or output:
        result_dict = {
            'team': team, 'season': season,
            'overall_strength': float(analysis_result.overall_strength) if analysis_result.overall_strength else None,
            'depth_score': float(analysis_result.depth_score) if analysis_result.depth_score else None,
        }
        if output:
            with open(output, 'w') as f:
                json.dump(result_dict, f, indent=2)
            click.echo(f"\nResults saved to {output}")
        else:
            click.echo(json.dumps(result_dict, indent=2))
    else:
        click.echo(f"\n{'='*60}")
        click.echo(f"SQUAD ANALYSIS: {team} ({season})")
        click.echo("=" * 60)
        if analysis_result.overall_strength:
            click.echo(f"\nOverall Strength: {analysis_result.overall_strength:.2f}")
        if analysis_result.depth_score:
            click.echo(f"Depth Score: {analysis_result.depth_score:.2f}")


@analysis.command(name='tournament-predict')
@click.option('--competition', '-c', default='six-nations', help='Competition name')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=1000, type=int, help='Number of Monte Carlo simulations')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
@click.option('--detailed-samples/--no-detailed-samples', default=False,
              help='Store detailed simulation samples for paths analysis (uses more memory)')
def tournament_predict(competition, season, model_path, data_dir, n_simulations, output, output_format, detailed_samples):
    """Predict tournament outcomes (requires rugby-ranking)."""
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for tournament prediction.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter

    # Map competition names to bonus point rules
    # Six Nations uses same bonus system as URC
    BONUS_RULES_MAP = {
        'six-nations': 'urc',
        'premiership': 'premiership',
        'top14': 'top14',
        'celtic': 'urc',
        'urc': 'urc',
    }
    bonus_rules = BONUS_RULES_MAP.get(competition, 'urc')

    if not data_dir:
        data_dir = str(find_data_dir())

    # Determine checkpoint name from model path
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        # Extract checkpoint name from path (e.g., ~/.cache/rugby_ranking/NAME/trace.nc)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Predicting {competition} {season}...")
    click.echo(f"Simulations: {n_simulations}")

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        # Only load files for the specific competition to speed up loading
        #pattern = f"{competition}-*.json"
        #click.echo(f"Loading {pattern} files...")
        dataset.load_json_files()

        # Load model from checkpoint (this restores team/player indices)
        click.echo(f"Loading model from checkpoint: {checkpoint_name}")
        model = RugbyModel()
        fitter = ModelFitter.load(checkpoint_name, model)
        trace = fitter.trace
    except Exception as e:
        click.echo(f"Error loading dataset/model: {e}", err=True)
        sys.exit(1)

    # Debug: show what competitions and seasons are available
    if len(dataset.matches) == 0:
        click.echo("Warning: No matches loaded from dataset!", err=True)
    else:
        competitions = set(m.competition for m in dataset.matches)
        seasons = set(m.season for m in dataset.matches)
        click.echo(f"Available competitions: {competitions}")
        click.echo(f"Available seasons: {seasons}")

    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining")

    # Handle edge cases
    if len(played_matches) == 0 and len(remaining_fixtures) == 0:
        click.echo(f"\nNo matches found for {competition} {season}", err=True)
        click.echo("Please check that the competition and season names are correct.", err=True)
        sys.exit(1)

    if len(remaining_fixtures) == 0:
        click.echo("\nAll matches have been played - no predictions needed!", err=True)
        sys.exit(0)

    if len(played_matches) == 0:
        click.echo("No matches played yet - predictions based on model priors")

    click.echo(f"Running {n_simulations} simulations...")

    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=remaining_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=detailed_samples  # Enable if user wants paths analysis later
    )

    if output_format == 'json' or output:
        result = {
            'competition': competition, 'season': season,
            'current_standings': prediction.current_standings.to_dict(orient='records'),
            'predicted_standings': prediction.predicted_standings.to_dict(orient='records'),
        }
        if prediction.position_probabilities is not None:
            result['position_probabilities'] = prediction.position_probabilities.to_dict(orient='records')
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            click.echo(f"\nResults saved to {output}")
        else:
            click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n{'='*60}")
        click.echo(f"TOURNAMENT PREDICTION: {competition.upper()} {season}")
        click.echo("=" * 60)
        click.echo("\nCurrent Standings:")
        click.echo(prediction.current_standings.to_string(index=False))

        click.echo("\n\nPredicted Match Results:")
        click.echo("-" * 60)
        if prediction.remaining_fixtures is not None and len(prediction.remaining_fixtures) > 0:
            for _, match in prediction.remaining_fixtures.iterrows():
                home_team = match.get('home_team', '?')
                away_team = match.get('away_team', '?')
                home_score = match.get('home_score_pred', 0)
                away_score = match.get('away_score_pred', 0)
                home_win_prob = match.get('home_win_prob', 0) * 100

                # Determine likely winner
                if home_win_prob > 50:
                    winner_indicator = f"{home_team} ({home_win_prob:.0f}%)"
                elif home_win_prob < 50:
                    winner_indicator = f"{away_team} ({100-home_win_prob:.0f}%)"
                else:
                    winner_indicator = "Toss-up"

                click.echo(f"{home_team:15} {home_score:5.0f} - {away_score:5.0f} {away_team:15}  [{winner_indicator}]")
        else:
            click.echo("No remaining fixtures")

        click.echo("\n\nPredicted Final Standings:")
        click.echo("-" * 60)
        click.echo(prediction.predicted_standings.to_string(index=False))


@analysis.command(name='paths-to-victory')
@click.option('--competition', '-c', default='six-nations', help='Competition name')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--team', '-t', required=True, help='Team name')
@click.option('--target-position', '-p', type=int, default=1, help='Target position (default: 1 for championship)')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=1000, type=int, help='Number of Monte Carlo simulations')
@click.option('--method', type=click.Choice(['auto', 'mcmc', 'combinatorial']), default='auto',
              help='Analysis method (default: auto)')
@click.option('--max-conditions', type=int, default=10, help='Maximum conditions to display')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
def paths_to_victory(competition, season, team, target_position, model_path, data_dir,
                     n_simulations, method, max_conditions, output, output_format):
    """Analyze paths for a team to achieve target position (requires rugby-ranking).

    This analyzes what needs to happen for a team to finish in a specific position,
    identifies critical games, and uses mutual information to rank game importance.

    Examples:
        rugby analysis paths-to-victory -t Scotland -p 1  # Scotland winning championship
        rugby analysis paths-to-victory -t Italy -p 4     # Italy finishing 4th
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for paths-to-victory analysis.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter
    from rugby_ranking.model.paths_to_victory import PathsAnalyzer

    # Map competition names to bonus point rules
    BONUS_RULES_MAP = {
        'six-nations': 'urc',
        'premiership': 'premiership',
        'top14': 'top14',
        'celtic': 'urc',
        'urc': 'urc',
    }
    bonus_rules = BONUS_RULES_MAP.get(competition, 'urc')

    if not data_dir:
        data_dir = str(find_data_dir())

    # Determine checkpoint name from model path
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Analyzing paths to position {target_position} for {team}...")
    click.echo(f"Competition: {competition} {season}")
    click.echo(f"Simulations: {n_simulations}")

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        dataset.load_json_files()

        # Load model from checkpoint
        click.echo(f"Loading model from checkpoint: {checkpoint_name}")
        model = RugbyModel()
        fitter = ModelFitter.load(checkpoint_name, model)
        trace = fitter.trace
    except Exception as e:
        click.echo(f"Error loading dataset/model: {e}", err=True)
        sys.exit(1)

    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining")

    if len(remaining_fixtures) == 0:
        click.echo("\nAll matches have been played - no paths analysis needed!", err=True)
        sys.exit(0)

    click.echo(f"Running {n_simulations} simulations with full sample tracking...")

    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    # Run prediction with return_samples=True to enable mutual information analysis
    prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=remaining_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=True  # This enables mutual information calculation
    )

    # Run paths analysis
    click.echo(f"\nAnalyzing paths using {method} method...")
    paths_analyzer = PathsAnalyzer(prediction, match_predictor)

    try:
        paths = paths_analyzer.analyze_paths(
            team=team,
            target_position=target_position,
            method=method,
            max_conditions=max_conditions
        )
    except Exception as e:
        click.echo(f"Error analyzing paths: {e}", err=True)
        sys.exit(1)

    if output_format == 'json' or output:
        result = {
            'team': team,
            'target_position': target_position,
            'probability': float(paths.probability),
            'method': paths.method,
            'narrative': paths.narrative,
            'critical_games': [
                {
                    'home_team': game[0][0],
                    'away_team': game[0][1],
                    'impact': float(game[1])
                }
                for game in paths.critical_games
            ],
            'conditions': [
                {
                    'game': {'home': cond.game[0], 'away': cond.game[1]},
                    'outcome': cond.outcome,
                    'frequency': float(cond.frequency),
                    'conditional_prob': float(cond.conditional_prob),
                    'importance': float(cond.importance),
                    'team_controls': cond.team_controls
                }
                for cond in paths.conditions
            ]
        }
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            click.echo(f"\nResults saved to {output}")
        else:
            click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n{'='*70}")
        click.echo(f"PATHS TO VICTORY: {team} finishing {target_position}")
        click.echo(f"Competition: {competition.upper()} {season}")
        click.echo("=" * 70)
        click.echo(f"\nProbability of finishing {target_position}: {paths.probability:.1%}")
        click.echo(f"Analysis method: {paths.method}")

        click.echo("\n" + paths.narrative)

        if paths.critical_games:
            click.echo(f"\n{'='*70}")
            click.echo("CRITICAL GAMES (ranked by impact on outcome)")
            click.echo("=" * 70)
            for i, (game, impact) in enumerate(paths.critical_games[:10], 1):
                home, away = game
                click.echo(f"{i:2}. {home:15} vs {away:15}  [Impact: {impact:+.1%}]")

        if paths.conditions:
            click.echo(f"\n{'='*70}")
            click.echo("KEY CONDITIONS")
            click.echo("=" * 70)
            for i, cond in enumerate(paths.conditions[:max_conditions], 1):
                home, away = cond.game
                control = "✓" if cond.team_controls else " "
                click.echo(f"{i:2}. [{control}] {home:15} vs {away:15}")
                click.echo(f"     Outcome needed: {cond.outcome}")
                click.echo(f"     Appears in: {cond.frequency:.1%} of winning scenarios")
                click.echo(f"     P(success|condition): {cond.conditional_prob:.1%}")
                click.echo(f"     Impact: {cond.importance:+.1%}")


@analysis.command(name='critical-games')
@click.option('--competition', '-c', default='six-nations', help='Competition name')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=1000, type=int, help='Number of Monte Carlo simulations')
@click.option('--top-n', type=int, default=10, help='Number of top games to show')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
def critical_games(competition, season, model_path, data_dir, n_simulations, top_n, output, output_format):
    """Identify most important games in tournament (requires rugby-ranking).

    Uses mutual information to identify which games have the greatest impact
    on championship outcomes across all teams.

    Examples:
        rugby analysis critical-games -c six-nations -s 2025-2026
        rugby analysis critical-games --top-n 5
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for critical games analysis.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter
    from rugby_ranking.model.paths_to_victory import PathsAnalyzer

    # Map competition names to bonus point rules
    BONUS_RULES_MAP = {
        'six-nations': 'urc',
        'premiership': 'premiership',
        'top14': 'top14',
        'celtic': 'urc',
        'urc': 'urc',
    }
    bonus_rules = BONUS_RULES_MAP.get(competition, 'urc')

    if not data_dir:
        data_dir = str(find_data_dir())

    # Determine checkpoint name from model path
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Identifying critical games for {competition} {season}...")
    click.echo(f"Simulations: {n_simulations}")

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        dataset.load_json_files()

        # Load model from checkpoint
        click.echo(f"Loading model from checkpoint: {checkpoint_name}")
        model = RugbyModel()
        fitter = ModelFitter.load(checkpoint_name, model)
        trace = fitter.trace
    except Exception as e:
        click.echo(f"Error loading dataset/model: {e}", err=True)
        sys.exit(1)

    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining")

    if len(remaining_fixtures) == 0:
        click.echo("\nAll matches have been played - no critical games to analyze!", err=True)
        sys.exit(0)

    click.echo(f"Running {n_simulations} simulations...")

    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    # Run prediction with return_samples=True to enable mutual information analysis
    prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=remaining_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=True
    )

    # Analyze critical games
    click.echo("\nAnalyzing game importance using mutual information...")
    paths_analyzer = PathsAnalyzer(prediction, match_predictor)

    try:
        critical_games_df = paths_analyzer.find_critical_games(top_n=top_n)
    except Exception as e:
        click.echo(f"Error finding critical games: {e}", err=True)
        sys.exit(1)

    if output_format == 'json' or output:
        result = {
            'competition': competition,
            'season': season,
            'critical_games': critical_games_df.to_dict(orient='records')
        }
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            click.echo(f"\nResults saved to {output}")
        else:
            click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n{'='*70}")
        click.echo(f"CRITICAL GAMES: {competition.upper()} {season}")
        click.echo("=" * 70)
        click.echo(f"\nTop {top_n} most important games (by impact on championship outcomes):\n")

        for i, row in critical_games_df.iterrows():
            home = row['home_team']
            away = row['away_team']
            impact = row['total_impact']
            date_str = f" on {row['date']}" if pd.notna(row.get('date')) else ""
            click.echo(f"{i+1:2}. {home:15} vs {away:15}  [Impact: {impact:.3f}]{date_str}")


@analysis.command(name='export-dashboard')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Rugby-Data json/ directory (default: auto-detect)')
@click.option('--output-dir', '-o', type=click.Path(), default='dashboard/data',
              help='Output directory for JSON files (default: dashboard/data)')
@click.option('--checkpoint', '-m', default=None,
              help='Model checkpoint name (default: fit a new model)')
@click.option('--seasons', '-n', type=int, default=3,
              help='Number of recent seasons to export (default: 3)')
def export_dashboard(data_dir, output_dir, checkpoint, seasons):
    """Export model data to JSON files for dashboard deployment (requires rugby-ranking).

    Exports team rankings, player rankings, match statistics, predictions,
    league tables, squad depth analysis, and more to a set of static JSON
    files suitable for powering a web dashboard.

    Examples:
        rugby analysis export-dashboard
        rugby analysis export-dashboard -m international-mini5
        rugby analysis export-dashboard -o /tmp/dashboard -n 2
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for dashboard export.", err=True)
        sys.exit(1)

    try:
        from rugby_ranking.tools.export_dashboard_data import export_dashboard_data
    except ImportError:
        click.echo(
            "Error: rugby_ranking.tools.export_dashboard_data not found.\n"
            "Please install a recent version of rugby-ranking.",
            err=True,
        )
        sys.exit(1)

    if not data_dir:
        data_dir = str(find_data_dir())

    export_dashboard_data(
        data_dir=Path(data_dir),
        output_dir=Path(output_dir),
        checkpoint_name=checkpoint,
        recent_seasons_only=seasons,
    )


@analysis.command(name='knockout-predict')
@click.option('--tournament', '-t', required=True,
              type=click.Choice(['urc', 'world-cup', 'champions-cup']),
              help='Tournament format')
@click.option('--competition', '-c', default='urc', help='Competition name (for data)')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=10000, type=int, help='Number of simulations')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
def knockout_predict(tournament, competition, season, model_path, data_dir,
                     n_simulations, output, output_format):
    """Predict knockout/playoff rounds with uncertain seeding (requires rugby-ranking).

    Simulates tournament knockout stages with cascading uncertainty from
    pool positions through to finals.

    Examples:
        rugby analysis knockout-predict -t urc -c celtic -s 2025-2026
        rugby analysis knockout-predict -t world-cup -n 20000 --format json
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for knockout predictions.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter
    from rugby_ranking.model.knockout_forecast import (
        TournamentTreeSimulator,
        URCPlayoffBracket,
        WorldCupBracket,
        ChampionsCupBracket,
        format_knockout_forecast,
    )

    # Map tournament names to bracket structures
    BRACKET_MAP = {
        'urc': URCPlayoffBracket(),
        'world-cup': WorldCupBracket(),
        'champions-cup': ChampionsCupBracket(),
    }

    bracket = BRACKET_MAP[tournament]

    if not data_dir:
        data_dir = str(find_data_dir())

    # Determine checkpoint name
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Predicting {tournament} knockout rounds...")
    click.echo(f"Simulations: {n_simulations}")

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        dataset.load_json_files()

        click.echo(f"Loading model from checkpoint: {checkpoint_name}")
        model = RugbyModel()
        fitter = ModelFitter.load(checkpoint_name, model)
        trace = fitter.trace
    except Exception as e:
        click.echo(f"Error loading dataset/model: {e}", err=True)
        sys.exit(1)

    # First, run season prediction to get pool position probabilities
    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining")

    # Run pool/league stage prediction
    click.echo(f"\nSimulating pool/league stage...")
    match_predictor = MatchPredictor(model, trace)

    BONUS_RULES_MAP = {
        'six-nations': 'urc',
        'premiership': 'premiership',
        'top14': 'top14',
        'celtic': 'urc',
        'urc': 'urc',
    }
    bonus_rules = BONUS_RULES_MAP.get(competition, 'urc')

    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)
    pool_prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=remaining_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=False,
    )

    # Now simulate knockout rounds
    click.echo(f"\nSimulating {tournament} knockout rounds...")
    knockout_simulator = TournamentTreeSimulator(
        match_predictor=match_predictor,
        bracket_structure=bracket,
        season=season,
    )

    forecast = knockout_simulator.simulate_knockout(
        pool_position_probabilities=pool_prediction.position_probabilities,
        n_simulations=n_simulations,
        pool_standings=pool_prediction.current_standings,
    )

    # Output results
    if output_format == 'json' or output:
        result = {
            'tournament': tournament,
            'competition': competition,
            'season': season,
            'winner_probabilities': forecast.winner_probabilities,
            'runner_up_probabilities': forecast.runner_up_probabilities,
            'stages': [
                {
                    'stage': stage.stage,
                    'team_probabilities': stage.team_probabilities,
                    'top_matchups': [
                        {'home': home, 'away': away, 'probability': prob}
                        for (home, away), prob in sorted(
                            stage.matchup_probabilities.items(),
                            key=lambda x: x[1],
                            reverse=True
                        )[:5]
                    ]
                }
                for stage in forecast.knockout_stages
            ],
        }

        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            click.echo(f"\nResults saved to {output}")
        else:
            click.echo(json.dumps(result, indent=2))
    else:
        formatted = format_knockout_forecast(forecast, top_n=10)
        click.echo("\n" + formatted)

        # Show most likely paths for top teams
        click.echo(f"\n{'='*70}")
        click.echo("MOST LIKELY PATHS TO FINAL:")
        click.echo("=" * 70)

        sorted_winners = sorted(
            forecast.winner_probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        for team, prob in sorted_winners:
            path = forecast.likely_paths.get(team, [])
            path_str = " → ".join(path) if path else "No path recorded"
            click.echo(f"{team:<30} ({prob:>5.1%}): {path_str}")
