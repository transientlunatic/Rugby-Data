# Automated Data Updates

This repository includes automated data fetching and updates via GitHub Actions.

## How It Works

The repository is configured to automatically update rugby match data:

- **Schedule**: Every Monday at midnight (UTC)
- **Manual Trigger**: Can be triggered manually from the GitHub Actions tab

## What Gets Updated

Currently, the automation updates:

- **URC (United Rugby Championship)**: Latest season data including:
  - Match results for completed games
  - Future fixtures (without results)
  - Player lineups, scores, substitutions, and cards (for completed matches)

## Manual Updates

You can manually trigger an update from the GitHub Actions interface:

1. Go to the "Actions" tab in the repository
2. Select "Update Rugby Data" workflow
3. Click "Run workflow"
4. Optionally specify:
   - A specific season (e.g., "2024-2025")
   - Dry run mode (to preview changes without committing)

## How to Run Locally

To update data locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Update current season (default)
python update_data.py

# Update specific season
python update_data.py --season "2024-2025"

# Dry run (preview changes)
python update_data.py --dry-run

# Update specific tournaments
python update_data.py -t urc
```

## Data Sources

### URC (United Rugby Championship)
- **Source**: InCrowd Sports API (rugby-union-feeds.incrowdsports.com)
- **Format**: JSON API
- **Reliability**: High - Official data feed
- **Coverage**: Complete match data including lineups, scores, and events

### Future Enhancements

Planned improvements include:

- Additional tournament support (Premiership, Top 14, European competitions)
- International matches integration
- Improved error handling and retry logic
- Data validation and consistency checks

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
