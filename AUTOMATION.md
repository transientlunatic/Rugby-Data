# Automated Data Updates

This repository includes automated data fetching and updates via GitHub Actions.

## How It Works

The repository is configured to automatically update rugby match data:

- **Schedule**: Every Monday at midnight (UTC)
- **Manual Trigger**: Can be triggered manually from the GitHub Actions tab

## What Gets Updated

Currently, the automation supports the following competitions, defined in `LEAGUE_CONFIGS` in `rugby/update.py`:

InCrowd Sports API (club competitions):
- **URC (United Rugby Championship)**: Latest season data including:
  - Match results for completed games
  - Future fixtures (without results)
  - Player lineups, scores, substitutions, and cards (for completed matches)
- **Gallagher Premiership**: English top-tier rugby league with complete match data
- **RFU Championship**: English second-tier rugby league with complete match data
- **Top 14**: French top-tier rugby league with complete match data
- **Pro D2**: French second-tier rugby league with complete match data
- **European Rugby Champions Cup**: Premier European club competition
- **European Rugby Challenge Cup**: Secondary European club competition

Wikipedia (internationals and competitions without an API feed):
- **Six Nations Championship**
- **Mid-year Internationals**
- **End-of-year Internationals**
- **Rugby World Cup** (World Cup years only)
- **Super Rugby**
- **Rugby Championship** (Argentina / Australia / New Zealand / South Africa)
- **Japan Rugby League One**
- **Currie Cup**
- **National Provincial Championship (NPC)**

Club competitions include the same detailed data structure with match results, player lineups, scoring events, and match officials when available. Wikipedia-sourced competitions include results and, where the source page has them, lineups and scoring events.

### Adding New Leagues

The system is designed to be easily extensible. To add support for a new league:

1. For a club competition on the InCrowd Sports API, obtain the competition ID and provider, then add an entry to the `LEAGUE_CONFIGS` dictionary in `rugby/update.py`:

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

2. For a competition without an API feed, add an entry with `'provider': 'wikipedia'` instead (see the internationals/Super Rugby/NPC entries in `rugby/update.py` for examples), and confirm `rugby/scrapers/six_nations.py`'s page-title logic resolves the right Wikipedia page for it.

3. The league will automatically be available via `rugby data update -t <code>` and GitHub Actions.

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
pip install .

# Update current season (default - URC)
rugby data update

# Update specific season
rugby data update --season "2024-2025"

# Dry run (preview changes)
rugby data update --dry-run

# Update specific tournaments
rugby data update -t premiership
rugby data update -t euro-champions
rugby data update -t top14

# Update all available tournaments
rugby data update -t all

# Update multiple specific tournaments
rugby data update -t urc -t premiership -t euro-champions

# Available tournament codes: urc, premiership, championship, top14, pro-d2,
# euro-champions, euro-challenge, six-nations, mid-year-internationals,
# end-of-year-internationals, world-cup, super-rugby, rugby-championship,
# japan-league-one, currie-cup, npc
```

## Data Sources

### InCrowd Sports API
- **Source**: rugby-union-feeds.incrowdsports.com
- **Provider**: rugbyviz
- **Format**: JSON API
- **Reliability**: High - Official data feed
- **Coverage**: Complete match data including lineups, scores, and events

| League Code | Competition ID | Description |
|-------------|---------------|-------------|
| urc | 1068 | United Rugby Championship (Celtic League / Pro12 / Pro14) |
| premiership | 1011 | Gallagher Premiership (English top-tier) |
| championship | 1051 | RFU Championship (English second-tier) |
| top14 | 1002 | French top-tier rugby |
| pro-d2 | 1013 | French second-tier rugby |
| euro-champions | 1008 | European Rugby Champions Cup |
| euro-challenge | 1026 | European Rugby Challenge Cup |

### Wikipedia
- **Format**: Wikitext, parsed by `rugby/scrapers/six_nations.py`
- **Reliability**: Medium - depends on page structure staying consistent
- **Coverage**: Results always; lineups and scoring events when the source page includes them

| League Code | Description |
|-------------|-------------|
| six-nations | Six Nations Championship |
| mid-year-internationals | Mid-year (summer) internationals |
| end-of-year-internationals | End-of-year (autumn) internationals |
| world-cup | Rugby World Cup (World Cup years only) |
| super-rugby | Super Rugby |
| rugby-championship | Rugby Championship (Argentina / Australia / New Zealand / South Africa) |
| japan-league-one | Japan Rugby League One |
| currie-cup | Currie Cup |
| npc | National Provincial Championship (New Zealand) |

### Known Issues

- **Japan Rugby League One**: the Wikipedia page is found and rugbybox templates are detected, but they currently fail to parse into matches (0 matches saved on every run). Needs debugging against the live page - see `rugby/scrapers/six_nations.py`'s `parse_rugbybox`/`_parse_rugbybox_params`.

### Future Enhancements

The system can be extended to support:

- Major League Rugby (United States / Canada)
- Rugby Europe Championship
- Rugby Europe Super Cup - pending API availability or alternative data source
- Improved error handling and retry logic
- Data validation and consistency checks

To add a new league, update the `LEAGUE_CONFIGS` dictionary in `rugby/update.py`.

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
