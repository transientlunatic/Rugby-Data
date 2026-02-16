# Rugby Rankings Widget Embedding Guide

This guide shows how to embed interactive rugby ranking visualizations in your blog posts or web pages.

## Quick Start

### 1. Include Required Libraries

Add these to your blog post `<head>`:

```html
<!-- D3.js for visualizations -->
<script src="https://d3js.org/d3.v7.min.js"></script>

<!-- Rugby Charts library -->
<link rel="stylesheet" href="https://transientlunatic.github.io/Rugby-Data/dashboard/css/dashboard.css">
<script src="https://transientlunatic.github.io/Rugby-Data/dashboard/js/rugby_charts.js"></script>
```

### 2. Add a Container Element

Where you want the visualization to appear:

```html
<div id="my-rugby-widget"></div>
```

### 3. Render the Widget

Add this script after your container:

```html
<script>
// Fetch data and render
fetch('https://transientlunatic.github.io/Rugby-Data/dashboard/data/team_offense.json')
    .then(r => r.json())
    .then(offenseData => {
        fetch('https://transientlunatic.github.io/Rugby-Data/dashboard/data/team_defense.json')
            .then(r => r.json())
            .then(defenseData => {
                RugbyCharts.renderTeamComparisonWidget({
                    container: '#my-rugby-widget',
                    offenseData: offenseData,
                    defenseData: defenseData,
                    season: 'cup-2023',
                    scoreType: 'tries',
                    teamType: 'international',  // or 'club' or 'all'
                    height: 500
                });
            });
    });
</script>
```

---

## Available Widgets

### 1. Team Comparison Widget (Offense vs Defense)

Shows teams plotted by offensive strength (x-axis) vs defensive strength (y-axis).

**Full Example:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Team Comparison</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link rel="stylesheet" href="https://transientlunatic.github.io/Rugby-Data/dashboard/css/dashboard.css">
    <script src="https://transientlunatic.github.io/Rugby-Data/dashboard/js/rugby_charts.js"></script>
</head>
<body>
    <h1>Rugby World Cup 2023: Team Comparison</h1>
    <p>Hover over points to see team names and exact values.</p>

    <div id="team-comparison"></div>

    <script>
    const BASE_URL = 'https://transientlunatic.github.io/Rugby-Data/dashboard/data';

    Promise.all([
        fetch(`${BASE_URL}/team_offense.json`).then(r => r.json()),
        fetch(`${BASE_URL}/team_defense.json`).then(r => r.json())
    ]).then(([offenseData, defenseData]) => {
        RugbyCharts.renderTeamComparisonWidget({
            container: '#team-comparison',
            offenseData: offenseData,
            defenseData: defenseData,
            season: 'cup-2023',
            scoreType: 'tries',
            teamType: 'international',
            height: 500
        });
    });
    </script>
</body>
</html>
```

**Parameters:**
- `container` (required): CSS selector for container element
- `offenseData` (required): Team offensive rankings data
- `defenseData` (required): Team defensive rankings data
- `season` (optional): Filter to specific season (e.g., 'cup-2023')
- `scoreType` (optional): 'tries', 'penalties', or 'conversions' (default: 'tries')
- `teamType` (optional): 'all', 'international', or 'club' (default: 'all')
- `height` (optional): Chart height in pixels (default: 500)

---

### 2. Player Comparison Widget

Horizontal bar chart showing player rankings with confidence intervals.

**Full Example:**

```html
<h1>Top Try Scorers</h1>
<div id="player-rankings"></div>

<script>
fetch('https://transientlunatic.github.io/Rugby-Data/dashboard/data/player_rankings.json')
    .then(r => r.json())
    .then(playerData => {
        RugbyCharts.renderPlayerComparisonWidget({
            container: '#player-rankings',
            playerData: playerData,
            scoreType: 'tries',
            topN: 15,
            height: 600
        });
    });
</script>
```

**Compare Specific Players:**

```javascript
RugbyCharts.renderPlayerComparisonWidget({
    container: '#player-comparison',
    playerData: playerData,
    players: ['Antoine Dupont', 'Finn Russell', 'Johnny Sexton'],  // Specific players only
    scoreType: 'tries',
    height: 400
});
```

**Parameters:**
- `container` (required): CSS selector
- `playerData` (required): Player rankings data
- `scoreType` (optional): 'tries', 'penalties', or 'conversions' (default: 'tries')
- `players` (optional): Array of specific player names to show
- `topN` (optional): Number of top players to show if `players` not specified (default: 20)
- `height` (optional): Chart height (default: 600)

---

### 3. Match Predictor Widget

Shows match prediction with narrative text, win probabilities, and score ranges.

**Full Example:**

```html
<h1>Ireland vs France Prediction</h1>
<div id="match-prediction"></div>

<script>
// You would typically fetch this from match_prediction_lookup.json
// For now, creating example data structure:
const prediction = {
    home_team: 'Ireland',
    away_team: 'France',
    home_score_mean: 23.4,
    home_score_std: 6.2,
    home_score_lower: 14,
    home_score_upper: 34,
    away_score_mean: 19.2,
    away_score_std: 5.8,
    away_score_lower: 10,
    away_score_upper: 30,
    home_win_prob: 0.62,
    away_win_prob: 0.35,
    draw_prob: 0.03
};

RugbyCharts.renderMatchPredictorWidget({
    container: '#match-prediction',
    prediction: prediction,
    showDistribution: true
});
</script>
```

**Parameters:**
- `container` (required): CSS selector
- `prediction` (required): Prediction object with structure shown above
- `showDistribution` (optional): Whether to show score distribution histogram (default: true)

**Prediction Object Structure:**
```javascript
{
    home_team: string,          // Home team name
    away_team: string,          // Away team name
    home_score_mean: number,    // Expected home score
    home_score_std: number,     // Standard deviation
    home_score_lower: number,   // 5th percentile
    home_score_upper: number,   // 95th percentile
    away_score_mean: number,    // Expected away score
    away_score_std: number,     // Standard deviation
    away_score_lower: number,   // 5th percentile
    away_score_upper: number,   // 95th percentile
    home_win_prob: number,      // Probability (0-1)
    away_win_prob: number,      // Probability (0-1)
    draw_prob: number           // Probability (0-1)
}
```

---

## Advanced: Loading Multiple Data Sources

For widgets that need multiple data files, use `Promise.all()`:

```javascript
const BASE_URL = 'https://transientlunatic.github.io/Rugby-Data/dashboard/data';

Promise.all([
    fetch(`${BASE_URL}/team_offense.json`).then(r => r.json()),
    fetch(`${BASE_URL}/team_defense.json`).then(r => r.json()),
    fetch(`${BASE_URL}/player_rankings.json`).then(r => r.json()),
]).then(([offenseData, defenseData, playerData]) => {
    // Now you can render multiple widgets with all data loaded

    RugbyCharts.renderTeamComparisonWidget({
        container: '#teams',
        offenseData: offenseData,
        defenseData: defenseData,
        season: 'cup-2023'
    });

    RugbyCharts.renderPlayerComparisonWidget({
        container: '#players',
        playerData: playerData,
        topN: 10
    });
});
```

---

## Filtering International vs Club Teams

All widgets support the `teamType` parameter to filter teams:

```javascript
// Show only international teams
RugbyCharts.renderTeamComparisonWidget({
    container: '#international-teams',
    offenseData: offenseData,
    defenseData: defenseData,
    teamType: 'international',  // Only show international teams
    scoreType: 'tries'
});

// Show only club teams
RugbyCharts.renderTeamComparisonWidget({
    container: '#club-teams',
    offenseData: offenseData,
    defenseData: defenseData,
    teamType: 'club',  // Only show club teams
    scoreType: 'tries'
});
```

**Team Type Classification:**
- Automatically determined from team name or competition
- International teams: World Cup, Six Nations, Rugby Championship, etc.
- Club teams: URC, Premiership, Top 14, Champions Cup, etc.

---

## Styling

The widgets use Bootstrap 5 classes for styling. You can customize with CSS:

```css
/* Customize widget container */
.match-predictor-widget {
    font-family: 'Your Font', sans-serif;
    max-width: 600px;
    margin: 0 auto;
}

/* Customize narrative text */
.prediction-narrative {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
}

/* Customize D3 tooltips */
.tooltip-d3 {
    background-color: rgba(0, 0, 0, 0.9) !important;
    color: white !important;
    border-radius: 4px !important;
}
```

---

## Data Sources

### Available JSON Files

All data is hosted at: `https://transientlunatic.github.io/Rugby-Data/dashboard/data/`

- `summary.json` - Dataset summary and metadata
- `team_offense.json` - Team offensive rankings (all seasons, all score types)
- `team_defense.json` - Team defensive rankings
- `player_rankings.json` - Player rankings (all score types)
- `team_strength_series.json` - Team strength over time
- `upcoming_predictions.json` - Upcoming match predictions
- `league_table_{competition}_{season}.json` - League tables
- `match_prediction_lookup.json` - Pre-computed match predictions (coming soon)

### Data Update Frequency

- **Weekly**: All data updates via automated GitHub Actions workflow
- Check `summary.json` for `generated_at` timestamp

---

## Low-Level Chart Functions

For more control, you can use the low-level D3 chart functions directly:

### `renderBarChartWithCI(options)`

Horizontal bar chart with confidence intervals.

```javascript
RugbyCharts.renderBarChartWithCI({
    container: '#my-chart',
    data: [{team: 'Scotland', mean: 5.2, lower: 4.8, upper: 5.6}, ...],
    labelKey: 'team',
    meanKey: 'mean',
    lowerKey: 'lower',
    upperKey: 'upper',
    color: '#4CAF50',
    height: 400,
    tooltipFormatter: (d) => `${d.team}: ${d.mean.toFixed(1)}`
});
```

### `renderScatterPlot(options)`

2D scatter plot.

```javascript
RugbyCharts.renderScatterPlot({
    container: '#scatter',
    data: [{team: 'Scotland', offense: 5.2, defense: 3.1}, ...],
    xKey: 'offense',
    yKey: 'defense',
    labelKey: 'team',
    xLabel: 'Offensive Strength',
    yLabel: 'Defensive Strength',
    height: 500
});
```

### `renderLineChart(options)`

Time-series line chart (supports multiple series).

```javascript
RugbyCharts.renderLineChart({
    container: '#trends',
    data: [{season: '2022-2023', team: 'Scotland', value: 4.8}, ...],
    xKey: 'season',
    yKey: 'value',
    seriesKey: 'team',
    yLabel: 'Strength',
    xLabel: 'Season',
    height: 400,
    yReversed: true  // For ranking charts (lower = better)
});
```

---

## Troubleshooting

### Widget Not Appearing

1. **Check console for errors**: Open browser DevTools (F12) and look for JavaScript errors
2. **Verify data loaded**: Check Network tab to ensure JSON files downloaded
3. **Check container exists**: Ensure the container element ID matches your CSS selector

### CORS Errors

If loading from a different domain, ensure CORS is properly configured. GitHub Pages serves files with correct CORS headers by default.

### Data Not Filtering

- Verify `season` matches exactly what's in the data (e.g., 'cup-2023' not 'cup_2023')
- Check `scoreType` is lowercase: 'tries', 'penalties', or 'conversions'
- Ensure `teamType` is one of: 'all', 'international', or 'club'

---

## Examples

See the [main dashboard](https://transientlunatic.github.io/Rugby-Data/) for live examples of all widgets in action.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/transientlunatic/Rugby-Data/issues)
- **Model Documentation**: [MODEL_EXPLAINED.md](https://github.com/transientlunatic/rugby-ranking/blob/main/MODEL_EXPLAINED.md)
- **Data Repository**: [Rugby-Data](https://github.com/transientlunatic/Rugby-Data)

---

*Last updated: February 2026*
