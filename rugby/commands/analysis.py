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
@click.option('--competition', '-c', required=True, help='Competition name (e.g., celtic, premiership)')
@click.option('--season', '-s', required=True, help='Season (e.g., 2025-2026)')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def league_table(competition, season, data_dir):
    """Display the league table for a competition.

    Examples:
        rugby analysis league-table -c celtic -s 2025-2026
        rugby analysis league-table -c premiership -s 2025-2026
    """
    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

    tournament = load_tournament(competition, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {competition} {season}", err=True)
        sys.exit(1)

    try:
        table = tournament.league_table()
        click.echo(f"\n{competition.upper()} {season} - League Table\n")
        click.echo(table.to_string(index=False))
    except Exception as e:
        click.echo(f"Error generating league table: {e}", err=True)
        sys.exit(1)


@analysis.command()
@click.option('--competition', '-c', required=True, help='Competition name (e.g., celtic, six-nations)')
@click.option('--season', '-s', required=True, help='Season (e.g., 2025-2026)')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def results(competition, season, data_dir):
    """Display match results for a competition.

    Examples:
        rugby analysis results -c celtic -s 2025-2026
        rugby analysis results -c six-nations -s 2025-2026
    """
    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

    tournament = load_tournament(competition, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {competition} {season}", err=True)
        sys.exit(1)

    try:
        results_df = tournament.results_table()
        click.echo(f"\n{competition.upper()} {season} - Results\n")
        click.echo(results_df.to_string(index=False))
    except Exception as e:
        click.echo(f"Error generating results: {e}", err=True)
        sys.exit(1)


@analysis.command(name='player-stats')
@click.argument('player')
@click.option('--competition', '-c', required=True, help='Competition name (e.g., six-nations, celtic)')
@click.option('--season', '-s', required=True, help='Season (e.g., 2025-2026)')
@click.option('--data-dir', '-d', type=click.Path(exists=True), default=None,
              help='Data directory (default: json/)')
def player_stats(player, competition, season, data_dir):
    """Display statistics for a player.

    Examples:
        rugby analysis player-stats "Finn Russell" -c six-nations -s 2025-2026
    """
    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

    tournament = load_tournament(competition, season, data_dir)
    if not tournament:
        click.echo(f"No data found for {competition} {season}", err=True)
        sys.exit(1)

    try:
        lineup_data = tournament.lineup_summary()
        player_data = lineup_data[lineup_data['name'].str.contains(player, case=False, na=False)]

        if player_data.empty:
            click.echo(f"No data found for player '{player}' in {competition} {season}", err=True)
            sys.exit(1)

        click.echo(f"\nPlayer Stats: {player}")
        click.echo(f"Competition: {competition} {season}\n")

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


@analysis.command(name='predict')
@click.option('--competition', '-c', default='six-nations', help='Competition name')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=1000, type=int, help='Number of Monte Carlo simulations')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
@click.option('--force-knockout/--no-force-knockout', default=None,
              help='Override automatic knockout detection')
@click.option('--detailed-samples/--no-detailed-samples', default=False,
              help='Store detailed simulation samples for paths analysis')
def predict(competition, season, model_path, data_dir, n_simulations, output,
            output_format, force_knockout, detailed_samples):
    """
    Predict tournament outcomes - auto-detects league vs knockout format.

    Examples:
        rugby analysis predict -c six-nations -s 2025-2026
        rugby analysis predict -c celtic -s 2024-2025 -n 5000
        rugby analysis predict -c premiership --force-knockout
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter
    from rugby_ranking.model.knockout_forecast import (
        TournamentTreeSimulator, URCPlayoffBracket,
        WorldCupBracket, ChampionsCupBracket
    )

    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

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

    # Determine checkpoint name
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Predicting {competition} {season}...")
    click.echo(f"Simulations: {n_simulations}")

    # Load data and model (with posterior caching now!)
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

    # Prepare season data
    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining")

    # Handle edge case: no matches found
    if len(played_matches) == 0 and len(remaining_fixtures) == 0:
        click.echo(f"\nNo matches found for {competition} {season}", err=True)
        click.echo("Please check that the competition and season names are correct.", err=True)
        click.echo(f"Available competitions: {', '.join(dataset.get_competition_names())}", err=True)
        sys.exit(1)

    # Detect knockout format (unless overridden)
    has_knockout = force_knockout if force_knockout is not None else \
                   _detect_knockout_format(remaining_fixtures, competition)

    if has_knockout:
        click.echo("Detected knockout stage - will predict both league and playoff rounds")

        # Filter out TBC matches (playoff brackets to be determined)
        # These will be predicted by the knockout simulator
        if len(remaining_fixtures) > 0 and 'home_team' in remaining_fixtures.columns:
            league_fixtures = remaining_fixtures[
                ~remaining_fixtures['home_team'].str.contains('TBC', case=False, na=False) &
                ~remaining_fixtures['away_team'].str.contains('TBC', case=False, na=False)
            ].copy()
        else:
            league_fixtures = remaining_fixtures.copy()

        n_playoff_matches = len(remaining_fixtures) - len(league_fixtures)
        if n_playoff_matches > 0:
            click.echo(f"Found {n_playoff_matches} playoff matches (TBC opponents)")
    else:
        league_fixtures = remaining_fixtures

    # Create predictors (uses posterior parameter caching now!)
    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    # Run league stage prediction
    click.echo(f"Running league stage simulation ({len(league_fixtures)} remaining league matches)...")
    league_prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=league_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=has_knockout or detailed_samples  # Need samples for knockout
    )

    # Run knockout prediction if detected
    knockout_forecast = None
    if has_knockout:
        click.echo("Running knockout stage simulation...")
        bracket = _infer_bracket_structure(competition, league_prediction)

        knockout_simulator = TournamentTreeSimulator(
            match_predictor=match_predictor,
            bracket_structure=bracket,
            season=season
        )

        knockout_forecast = knockout_simulator.simulate_knockout(
            pool_position_probabilities=league_prediction.position_probabilities,
            n_simulations=n_simulations,
            pool_standings=league_prediction.current_standings
        )

    # Output results
    _output_prediction_results(
        league_prediction, knockout_forecast,
        competition, season, output, output_format
    )


def _detect_knockout_format(remaining_fixtures, competition):
    """
    Detect if tournament has knockout stage by checking for:
    1. TBC (To Be Confirmed) teams - indicates playoff brackets with unknown opponents
    2. Stage markers (QF, SF, Final) in fixture data
    3. Known knockout competitions near end of season
    """
    # Check for TBC teams - strong indicator of playoff/knockout fixtures
    if 'home_team' in remaining_fixtures.columns and 'away_team' in remaining_fixtures.columns:
        teams = pd.concat([remaining_fixtures['home_team'], remaining_fixtures['away_team']])
        if 'TBC' in teams.values or any('TBC' in str(team).upper() for team in teams.dropna()):
            return True

    # Check for stage column with knockout markers
    if 'stage' in remaining_fixtures.columns:
        knockout_stages = {'QF', 'SF', 'FINAL', 'R16', 'BRONZE', 'PLAYOFF'}
        stages = set(str(s).upper() for s in remaining_fixtures['stage'].dropna())
        if knockout_stages & stages:
            return True

    # Known knockout competitions - check if near playoffs
    knockout_comps = {'urc', 'celtic', 'champions-cup', 'euro-champions', 'world-cup'}
    if any(kc in competition.lower() for kc in knockout_comps):
        # If less than 30 remaining matches, likely in playoff phase
        if len(remaining_fixtures) < 30:
            return True

    return False


def _infer_bracket_structure(competition, league_prediction):
    """Infer bracket structure from competition name."""
    from rugby_ranking.model.knockout_forecast import (
        URCPlayoffBracket, WorldCupBracket, ChampionsCupBracket
    )

    comp_lower = competition.lower()

    if 'world-cup' in comp_lower or 'rugby-world-cup' in comp_lower:
        return WorldCupBracket()
    elif 'champions' in comp_lower or 'euro-champions' in comp_lower:
        return ChampionsCupBracket()
    elif 'urc' in comp_lower or 'celtic' in comp_lower:
        return URCPlayoffBracket()

    # Fallback: choose by number of teams
    n_teams = len(league_prediction.current_standings)
    return URCPlayoffBracket() if n_teams <= 10 else ChampionsCupBracket()


def _output_prediction_results(league_pred, knockout_pred, competition, season,
                                output_file, output_format):
    """Output combined league and knockout predictions."""
    if output_format == 'json' or output_file:
        result = {
            'competition': competition,
            'season': season,
            'league': {
                'current_standings': league_pred.current_standings.to_dict(orient='records'),
                'predicted_standings': league_pred.predicted_standings.to_dict(orient='records'),
            }
        }

        if league_pred.position_probabilities is not None:
            result['league']['position_probabilities'] = \
                league_pred.position_probabilities.to_dict(orient='records')

        if knockout_pred:
            result['knockout'] = {
                'winner_probabilities': knockout_pred.winner_probabilities,
                'runner_up_probabilities': knockout_pred.runner_up_probabilities,
            }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            click.echo(f"\nResults saved to {output_file}")
        else:
            click.echo(json.dumps(result, indent=2))
    else:
        # Table output
        click.echo(f"\n{'='*70}")
        click.echo(f"PREDICTION: {competition.upper()} {season}")
        click.echo("=" * 70)

        # Show predicted match results instead of current standings
        click.echo("\nPredicted Match Results:")
        click.echo("-" * 70)
        if league_pred.remaining_fixtures is not None and len(league_pred.remaining_fixtures) > 0:
            for _, match in league_pred.remaining_fixtures.iterrows():
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
        click.echo(league_pred.predicted_standings.to_string(index=False))

        if knockout_pred:
            click.echo(f"\n{'='*70}")
            click.echo("KNOCKOUT STAGE PREDICTIONS")
            click.echo("=" * 70)

            click.echo("\nTournament Winner Probabilities:")
            sorted_winners = sorted(knockout_pred.winner_probabilities.items(),
                                    key=lambda x: x[1], reverse=True)
            for team, prob in sorted_winners[:10]:
                click.echo(f"  {team:<30} {prob:>6.1%}")


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
    """Predict tournament outcomes (requires rugby-ranking).

    DEPRECATED: Use 'rugby analysis predict' instead.
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for tournament prediction.", err=True)
        sys.exit(1)

    # Show deprecation warning
    click.secho("Warning: 'tournament-predict' is deprecated. Use 'rugby analysis predict' instead.",
                fg='yellow', err=True)
    click.echo()

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter

    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

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

    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

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

    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

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


@analysis.command(name='season-standings')
@click.option('--competition', '-c', default='six-nations', help='Competition name')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=1000, type=int, help='Number of Monte Carlo simulations')
@click.option('--format', 'output_format', type=click.Choice(['markdown', 'json']),
              default='markdown', help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file')
def season_standings(competition, season, model_path, data_dir, n_simulations, output_format, output):
    """Show position probability table for a league season (requires rugby-ranking).

    Outputs a table showing the probability of each team finishing in each
    position, highlighting the most likely finishing position for each team.

    Examples:
        rugby analysis season-standings -c six-nations -s 2025-2026
        rugby analysis season-standings -c celtic -s 2025-2026 -n 5000
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for season standings.", err=True)
        sys.exit(1)

    from rugby_ranking.model.season_predictor import SeasonPredictor
    from rugby_ranking.model.predictions import MatchPredictor
    from rugby_ranking.model.core import RugbyModel
    from rugby_ranking.model.data import MatchDataset
    from rugby_ranking.model.data_utils import prepare_season_data
    from rugby_ranking.model.inference import ModelFitter

    # Competition name aliases (URC files are named 'celtic')
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    competition = COMPETITION_ALIASES.get(competition, competition)

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

    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Computing position probabilities for {competition} {season}...", err=True)
    click.echo(f"Simulations: {n_simulations}", err=True)

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        dataset.load_json_files()

        click.echo(f"Loading model from checkpoint: {checkpoint_name}", err=True)
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

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining", err=True)

    if len(played_matches) == 0 and len(remaining_fixtures) == 0:
        click.echo(f"\nNo matches found for {competition} {season}", err=True)
        sys.exit(1)

    click.echo(f"Running {n_simulations} simulations...", err=True)

    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=remaining_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=False,
    )

    pos_probs = prediction.position_probabilities
    if pos_probs is None:
        click.echo("Error: Position probabilities not available for this prediction.", err=True)
        sys.exit(1)

    # Normalise: ensure teams are in the index (not a column)
    if 'team' in pos_probs.columns:
        pos_probs = pos_probs.set_index('team')

    # Extract position columns (e.g. 'P(pos 1)', 'P(pos 2)', ...)
    pos_cols = [c for c in pos_probs.columns if c.startswith('P(pos ')]
    pos_cols_sorted = sorted(pos_cols, key=lambda c: int(c.split('P(pos ')[1].rstrip(')')))
    n_positions = len(pos_cols_sorted)

    if output_format == 'json':
        result = {
            'competition': competition,
            'season': season,
            'position_probabilities': pos_probs[pos_cols_sorted + ['most_likely_position']].to_dict(orient='index')
        }
        text = json.dumps(result, indent=2)
        if output:
            with open(output, 'w') as f:
                f.write(text)
            click.echo(f"Results saved to {output}", err=True)
        else:
            click.echo(text)
        return

    # Build ordinal labels: 1st, 2nd, 3rd, 4th, ...
    def ordinal(n):
        if 11 <= n <= 13:
            return f"{n}th"
        return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"

    position_labels = [ordinal(i + 1) for i in range(n_positions)]

    # Build markdown table
    col_width = 7  # width of each position column
    team_width = max(len(t) for t in pos_probs.index) + 2

    header_cells = [f"{'Team':<{team_width}}"]
    for lbl in position_labels:
        header_cells.append(f"{lbl:^{col_width}}")
    header_cells.append(f"{'Most likely':^{col_width + 4}}")
    header_line = "| " + " | ".join(header_cells) + " |"

    sep_cells = ["-" * team_width]
    for _ in position_labels:
        sep_cells.append("-" * col_width + ":")
    sep_cells.append("-" * (col_width + 4) + ":")
    sep_line = "| " + " | ".join(sep_cells) + " |"

    lines = [
        f"\n**Position probabilities — {competition.upper()} {season}**\n",
        header_line,
        sep_line,
    ]

    # Sort teams by most likely position, then by probability of that position
    def sort_key(team):
        most_likely = pos_probs.loc[team, 'most_likely_position'] \
            if 'most_likely_position' in pos_probs.columns else 0
        best_col = f"P(pos {most_likely})"
        best_prob = pos_probs.loc[team, best_col] if best_col in pos_probs.columns else 0.0
        return (most_likely, -best_prob)

    teams_sorted = sorted(pos_probs.index, key=sort_key)

    for team in teams_sorted:
        most_likely = pos_probs.loc[team, 'most_likely_position'] \
            if 'most_likely_position' in pos_probs.columns else None

        row_cells = [f"{team:<{team_width}}"]
        for i, col in enumerate(pos_cols_sorted):
            pct = pos_probs.loc[team, col] * 100
            pos_num = i + 1
            cell_str = f"{pct:.0f}%" if pct >= 0.5 else "<1%"
            if pos_num == most_likely:
                cell_str = f"**{cell_str}**"
            row_cells.append(f"{cell_str:^{col_width}}")

        ml_label = ordinal(most_likely) if most_likely else "?"
        row_cells.append(f"{'**' + ml_label + '**':^{col_width + 4}}")
        lines.append("| " + " | ".join(row_cells) + " |")

    table = "\n".join(lines) + "\n"

    if output:
        with open(output, 'w') as f:
            f.write(table)
        click.echo(f"Results saved to {output}", err=True)
    else:
        click.echo(table)


@analysis.command(name='playoff-bracket')
@click.option('--competition', '-c', required=True, help='Competition name (urc, celtic, champions-cup, world-cup)')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=5000, type=int, help='Number of Monte Carlo simulations')
@click.option('--top-matchups', type=int, default=5, help='Most likely matchups to show per stage')
@click.option('--format', 'output_format', type=click.Choice(['markdown', 'json']),
              default='markdown', help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file')
def playoff_bracket(competition, season, model_path, data_dir, n_simulations,
                    top_matchups, output_format, output):
    """Show likely playoff bracket with matchup probabilities (requires rugby-ranking).

    Runs a full league + knockout simulation and renders the most probable
    matchups at each stage, together with team qualification probabilities
    and tournament winner odds.

    Examples:
        rugby analysis playoff-bracket -c urc -s 2025-2026
        rugby analysis playoff-bracket -c celtic -s 2025-2026 -n 10000
        rugby analysis playoff-bracket -c champions-cup -s 2024-2025
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for playoff bracket.", err=True)
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
    )

    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    data_competition = COMPETITION_ALIASES.get(competition, competition)

    BRACKET_MAP = {
        'urc':           URCPlayoffBracket(),
        'celtic':        URCPlayoffBracket(),
        'world-cup':     WorldCupBracket(),
        'champions-cup': ChampionsCupBracket(),
    }
    bracket = BRACKET_MAP.get(competition)
    if not bracket:
        # Attempt to infer from name
        comp_lower = competition.lower()
        if 'world' in comp_lower:
            bracket = WorldCupBracket()
        elif 'champions' in comp_lower or 'euro' in comp_lower:
            bracket = ChampionsCupBracket()
        else:
            bracket = URCPlayoffBracket()

    BONUS_RULES_MAP = {
        'six-nations': 'urc',
        'premiership': 'premiership',
        'top14': 'top14',
        'celtic': 'urc',
        'urc': 'urc',
    }
    bonus_rules = BONUS_RULES_MAP.get(data_competition, 'urc')

    if not data_dir:
        data_dir = str(find_data_dir())

    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Simulating playoff bracket for {competition} {season}...", err=True)
    click.echo(f"Simulations: {n_simulations}", err=True)

    data_dir = Path(data_dir)

    try:
        dataset = MatchDataset(data_dir, fuzzy_match_names=False)
        dataset.load_json_files()

        click.echo(f"Loading model from checkpoint: {checkpoint_name}", err=True)
        model = RugbyModel()
        fitter = ModelFitter.load(checkpoint_name, model)
        trace = fitter.trace
    except Exception as e:
        click.echo(f"Error loading dataset/model: {e}", err=True)
        sys.exit(1)

    try:
        played_matches, remaining_fixtures = prepare_season_data(
            dataset, season=season, competition=data_competition, include_tries=True
        )
    except Exception as e:
        click.echo(f"Error preparing season data: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(played_matches)} played, {len(remaining_fixtures)} remaining", err=True)

    if len(played_matches) == 0 and len(remaining_fixtures) == 0:
        click.echo(f"\nNo matches found for {competition} {season}", err=True)
        sys.exit(1)

    # Filter out TBC playoff fixtures - pool stage only
    if 'home_team' in remaining_fixtures.columns:
        league_fixtures = remaining_fixtures[
            ~remaining_fixtures['home_team'].str.contains('TBC', case=False, na=False) &
            ~remaining_fixtures['away_team'].str.contains('TBC', case=False, na=False)
        ].copy()
    else:
        league_fixtures = remaining_fixtures.copy()

    click.echo("Simulating league stage...", err=True)
    match_predictor = MatchPredictor(model, trace)
    season_predictor = SeasonPredictor(match_predictor, competition=bonus_rules)

    pool_prediction = season_predictor.predict_season(
        played_matches=played_matches,
        remaining_fixtures=league_fixtures,
        season=season,
        n_simulations=n_simulations,
        return_samples=False,
    )

    click.echo("Simulating knockout stages...", err=True)
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

    if output_format == 'json':
        result = {
            'competition': competition,
            'season': season,
            'bracket': bracket.name,
            'stages': [
                {
                    'stage': stage.stage,
                    'team_probabilities': stage.team_probabilities,
                    'top_matchups': [
                        {'home': home, 'away': away, 'probability': prob}
                        for (home, away), prob in sorted(
                            stage.matchup_probabilities.items(),
                            key=lambda x: x[1], reverse=True
                        )[:top_matchups]
                    ],
                }
                for stage in forecast.knockout_stages
            ],
            'winner_probabilities': forecast.winner_probabilities,
            'runner_up_probabilities': forecast.runner_up_probabilities,
        }
        text = json.dumps(result, indent=2)
        if output:
            with open(output, 'w') as f:
                f.write(text)
            click.echo(f"Results saved to {output}", err=True)
        else:
            click.echo(text)
        return

    # --- Markdown rendering ---
    team_width = max(
        (len(t) for stage in forecast.knockout_stages
         for t in stage.team_probabilities),
        default=15
    ) + 2

    lines = [f"\n**{bracket.name} — {season}**\n"]

    for stage_result in forecast.knockout_stages:
        stage_label = {
            'R16': 'Round of 16',
            'QF': 'Quarter-Finals',
            'SF': 'Semi-Finals',
            'Bronze': 'Bronze Final (3rd place)',
            'Final': 'Final',
        }.get(stage_result.stage, stage_result.stage)

        lines.append(f"### {stage_label}\n")

        # Most likely matchups
        sorted_matchups = sorted(
            stage_result.matchup_probabilities.items(),
            key=lambda x: x[1], reverse=True
        )[:top_matchups]

        if sorted_matchups:
            lines.append(f"| {'Home':<{team_width}} | {'Away':<{team_width}} | {'Prob':>6} |")
            lines.append(f"| {'-'*team_width} | {'-'*team_width} | {'------':>6} |")
            for (home, away), prob in sorted_matchups:
                lines.append(
                    f"| {home:<{team_width}} | {away:<{team_width}} | {prob:>5.0%} |"
                )
            lines.append("")

        # Team qualification probabilities
        sorted_teams = sorted(
            stage_result.team_probabilities.items(),
            key=lambda x: x[1], reverse=True
        )
        lines.append(f"| {'Team':<{team_width}} | {'P(qualify)':>10} |")
        lines.append(f"| {'-'*team_width} | {'----------':>10} |")
        for team, prob in sorted_teams:
            prob_str = f"**{prob:.0%}**" if prob == max(stage_result.team_probabilities.values()) else f"{prob:.0%}"
            lines.append(f"| {team:<{team_width}} | {prob_str:>10} |")
        lines.append("")

    # Tournament winner table
    lines.append("### Tournament winner\n")
    sorted_winners = sorted(
        forecast.winner_probabilities.items(),
        key=lambda x: x[1], reverse=True
    )
    lines.append(f"| {'Team':<{team_width}} | {'P(win)':>8} | {'P(final)':>9} |")
    lines.append(f"| {'-'*team_width} | {'--------':>8} | {'---------':>9} |")
    max_win_prob = sorted_winners[0][1] if sorted_winners else 0
    for team, win_prob in sorted_winners:
        runner_up_prob = forecast.runner_up_probabilities.get(team, 0.0)
        final_prob = win_prob + runner_up_prob
        win_str = f"**{win_prob:.0%}**" if win_prob == max_win_prob else f"{win_prob:.0%}"
        lines.append(f"| {team:<{team_width}} | {win_str:>8} | {final_prob:>9.0%} |")

    table = "\n".join(lines) + "\n"

    if output:
        with open(output, 'w') as f:
            f.write(table)
        click.echo(f"Results saved to {output}", err=True)
    else:
        click.echo(table)


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
@click.option('--competition', '-c', required=True,
              type=click.Choice(['urc', 'celtic', 'world-cup', 'champions-cup']),
              help='Competition name (urc, world-cup, champions-cup)')
@click.option('--season', '-s', default='2025-2026', help='Season')
@click.option('--model-path', '-m', type=click.Path(), help='Path to trained model checkpoint')
@click.option('--data-dir', '-d', type=click.Path(exists=True), help='Data directory')
@click.option('--n-simulations', '-n', default=10000, type=int, help='Number of simulations')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']),
              default='table', help='Output format')
def knockout_predict(competition, season, model_path, data_dir,
                     n_simulations, output, output_format):
    """Predict knockout/playoff rounds with uncertain seeding (requires rugby-ranking).

    DEPRECATED: Use 'rugby analysis predict --force-knockout' instead.

    Simulates tournament knockout stages with cascading uncertainty from
    pool positions through to finals.

    Examples:
        rugby analysis knockout-predict -c urc -s 2025-2026
        rugby analysis knockout-predict -c world-cup -s 2023 -n 20000 --format json
    """
    if not check_rugby_ranking_available():
        click.echo("Error: rugby-ranking package is required for knockout predictions.", err=True)
        sys.exit(1)

    # Show deprecation warning
    click.secho("Warning: 'knockout-predict' is deprecated. Use 'rugby analysis predict --force-knockout' instead.",
                fg='yellow', err=True)
    click.echo()

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

    # Map competition names to bracket structures
    BRACKET_MAP = {
        'urc': URCPlayoffBracket(),
        'celtic': URCPlayoffBracket(),  # Alias for URC
        'world-cup': WorldCupBracket(),
        'champions-cup': ChampionsCupBracket(),
    }

    bracket = BRACKET_MAP.get(competition)
    if not bracket:
        click.echo(f"Error: No bracket structure defined for '{competition}'", err=True)
        click.echo(f"Supported competitions: {', '.join(BRACKET_MAP.keys())}", err=True)
        sys.exit(1)

    # For data loading, map 'urc' to 'celtic' (filename convention)
    COMPETITION_ALIASES = {
        'urc': 'celtic',
    }
    data_competition = COMPETITION_ALIASES.get(competition, competition)

    if not data_dir:
        data_dir = str(find_data_dir())

    # Determine checkpoint name
    if not model_path:
        checkpoint_name = 'international-mini5'
    else:
        model_path = Path(model_path)
        checkpoint_name = model_path.parent.name if model_path.name == 'trace.nc' else model_path.stem

    click.echo(f"Predicting {competition} knockout rounds...")
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
            dataset, season=season, competition=data_competition, include_tries=True
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
