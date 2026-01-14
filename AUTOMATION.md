# Automated Data Updates

This repository includes automated data fetching and updates via GitHub Actions.

## How It Works

The repository is configured to automatically update rugby match data:

- **Schedule**: Every Monday at midnight (UTC)
- **Manual Trigger**: Can be triggered manually from the GitHub Actions tab

## What Gets Updated

Currently, the automation supports the following leagues:

- **URC (United Rugby Championship)**: Latest season data including:
  - Match results for completed games
  - Future fixtures (without results)
  - Player lineups, scores, substitutions, and cards (for completed matches)

- **Gallagher Premiership**: English top-tier rugby league with complete match data

- **Top 14**: French top-tier rugby league with complete match data

- **Pro D2**: French second-tier rugby league with complete match data

- **European Rugby Champions Cup**: Premier European club competition

- **European Rugby Challenge Cup**: Secondary European club competition

All leagues include the same detailed data structure with match results, player lineups, scoring events, and match officials when available.

### Adding New Leagues

The system is designed to be easily extensible. To add support for a new league:

1. Obtain the competition ID and provider from the InCrowd Sports API
2. Add an entry to the `LEAGUE_CONFIGS` dictionary in `update_data.py`:

```python
LEAGUE_CONFIGS = {
    'urc': {...},
    'premiership': {
        'comp_id': 1011,  # Competition ID from API
        'provider': 'rugbyviz',
        'name': 'Gallagher Premiership',
        'filename_prefix': 'premiership'
    }
}
```

3. The league will automatically be available via CLI and GitHub Actions

## Manual Updates

You can manually trigger an update from the GitHub Actions interface:

1. Go to the "Actions" tab in the repository
2. Select "Update Rugby Data" workflow
3. Click "Run workflow"
4. Optionally specify:
   - A specific season (e.g., "2024-2025")
   - Tournaments to update (e.g., "urc" or "all")
   - Dry run mode (to preview changes without committing)

## How to Run Locally

To update data locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Update current season (default - URC)
python update_data.py

# Update specific season
python update_data.py --season "2024-2025"

# Dry run (preview changes)
python update_data.py --dry-run

# Update specific tournaments
python update_data.py -t premiership
python update_data.py -t euro-champions
python update_data.py -t top14

# Update all available tournaments
python update_data.py -t all

# Update multiple specific tournaments
python update_data.py -t urc -t premiership -t euro-champions

# Available tournament codes: urc, premiership, top14, pro-d2, euro-champions, euro-challenge
```

## Data Sources

All supported leagues use the same data source:

### InCrowd Sports API
- **Source**: rugby-union-feeds.incrowdsports.com
- **Provider**: rugbyviz
- **Format**: JSON API
- **Reliability**: High - Official data feed
- **Coverage**: Complete match data including lineups, scores, and events

#### Supported Competitions

| League | Competition ID | Description |
|--------|---------------|-------------|
| URC | 1068 | United Rugby Championship (Celtic League / Pro12 / Pro14) |
| Premiership | 1011 | Gallagher Premiership (English top-tier) |
| Top 14 | 1002 | French top-tier rugby |
| Pro D2 | 1013 | French second-tier rugby |
| Euro Champions Cup | 1008 | European Rugby Champions Cup |
| Euro Challenge Cup | 1026 | European Rugby Challenge Cup |

### Future Enhancements

The system can be extended to support:

- RFU Championship (English second-tier) - pending API availability
- International matches integration - requires different data source
- Improved error handling and retry logic
- Data validation and consistency checks

To add a new league, simply update the `LEAGUE_CONFIGS` dictionary in `update_data.py`.

## Troubleshooting

If the automation fails:

1. Check the GitHub Actions logs for specific errors
2. Verify that the data source APIs are accessible
3. Check if there are any structural changes to the API responses
4. Run manually with `--dry-run` to diagnose issues

## Contributing

If you notice any issues with the automated updates:

1. Check existing issues in the repository
2. Open a new issue with details about the problem
3. Include the workflow run ID if applicable
