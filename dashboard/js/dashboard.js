// Rugby Dashboard JavaScript with D3.js

// Global state
const state = {
    summary: null,
    teamOffense: null,
    teamDefense: null,
    playerRankings: null,
    matchStats: null,
    teamStats: null,
    teamStrengthSeries: null,
    teamFinishPositions: null,
    upcomingPredictions: null,
    pathsToVictory: null,
    squadDepth: null,
    leagueTableData: {},
    seasonPredictionData: {},
    heatmapData: {},
    selectedLeagueTableCompetition: null,
    selectedLeagueTableSeason: null,
    selectedSeasonPredictionCompetition: null,
    selectedSeasonPredictionSeason: null,
    selectedHeatmapCompetition: null,
    selectedHeatmapSeason: null,
    selectedSeason: null,
    selectedScoreType: 'tries',
    selectedRankLimit: 20
};

// Heatmap rendering stub (to be implemented with D3)
function renderHeatmap(data, teams, container) {
    // Placeholder: implement D3 heatmap rendering here
    // data: 2D array (teams x teams), teams: array of team names
    // container: selector string (e.g., '#heatmap-container')
    const el = document.querySelector(container);
    if (!el) return;
    el.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
}

async function loadHeatmapData() {
    const dataDir = 'data/';
    const competitions = [
        'six-nations', 'premiership', 'celtic', 'pro-d2', 'top14', 'euro-champions', 'euro-challenge',
        'mid-year-internationals', 'end-of-year-internationals', 'championship'
    ];
    const seasons = state.summary.seasons || [];
    state.heatmapData = {};
    for (const comp of competitions) {
        for (const season of seasons) {
            const file = `${dataDir}team_heatmap_${comp}_${season}.json`;
            state.heatmapData[`${comp}_${season}`] = await loadJsonSafe(file, null);
        }
    }
}

function populateHeatmapSelects() {
    const compSelect = document.getElementById('heatmap-competition');
    const seasonSelect = document.getElementById('heatmap-season');
    if (!compSelect || !seasonSelect) return;
    const competitions = [...new Set(Object.keys(state.heatmapData).map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];
    compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    state.selectedHeatmapCompetition = competitions[0] || '';
    state.selectedHeatmapSeason = seasons[seasons.length-1] || '';
}

function updateHeatmap() {
    const container = '#heatmap-container';
    const comp = state.selectedHeatmapCompetition;
    const season = state.selectedHeatmapSeason;
    const key = `${comp}_${season}`;
    const dataObj = state.heatmapData[key];
    const el = document.querySelector(container);
    if (!el) return;
    if (!comp || !season) {
        el.innerHTML = '<div class="text-muted">Select competition and season.</div>';
        return;
    }
    if (!dataObj || !dataObj.matrix || !dataObj.teams) {
        el.innerHTML = '<div class="text-muted">No heatmap data available for this selection.</div>';
        return;
    }
    renderHeatmap(dataObj.matrix, dataObj.teams, container);
}
function updateLeagueTable() {
    const tbody = document.querySelector('#league-table tbody');
    if (!tbody) return;
    const comp = state.selectedLeagueTableCompetition;
    const season = state.selectedLeagueTableSeason;
    if (!comp || !season) {
        tbody.innerHTML = '<tr><td colspan="14">Select competition and season.</td></tr>';
        return;
    }
    const key = `${comp}_${season}`;
    const data = state.leagueTableData[key];
    if (!data || !Array.isArray(data)) {
        tbody.innerHTML = '<tr><td colspan="14">No data available for this selection.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(row => `
        <tr>
            <td>${row.position}</td>
            <td><strong>${row.team}</strong></td>
            <td>${row.played}</td>
            <td>${row.won}</td>
            <td>${row.drawn}</td>
            <td>${row.lost}</td>
            <td>${row.points_for}</td>
            <td>${row.points_against}</td>
            <td>${row.points_diff}</td>
            <td>${row.tries_for}</td>
            <td>${row.tries_against}</td>
            <td>${row.bonus_points}</td>
            <td>${row.match_points}</td>
            <td>${row.total_points}</td>
        </tr>
    `).join('');
}

function updateSeasonPrediction() {
    const tbody = document.querySelector('#season-prediction-table tbody');
    if (!tbody) return;
    const comp = state.selectedSeasonPredictionCompetition;
    const season = state.selectedSeasonPredictionSeason;
    if (!comp || !season) {
        tbody.innerHTML = '<tr><td colspan="5">Select competition and season.</td></tr>';
        return;
    }
    const key = `${comp}_${season}`;
    const data = state.seasonPredictionData[key];
    if (!data || !Array.isArray(data)) {
        tbody.innerHTML = '<tr><td colspan="5">No data available for this selection.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(row => `
        <tr>
            <td><strong>${row.team}</strong></td>
            <td>${row.expected_points}</td>
            <td>${row.expected_wins}</td>
            <td>${row.expected_diff}</td>
            <td>${row.predicted_position}</td>
        </tr>
    `).join('');
}
// Dynamically load all league table and season prediction files
async function loadLeagueTableAndSeasonPredictionData() {
    const dataDir = 'data/';
    // List of files is static, but could be made dynamic with a manifest
    const competitions = [
        'six-nations', 'premiership', 'celtic', 'pro-d2', 'top14', 'euro-champions', 'euro-challenge',
        'mid-year-internationals', 'end-of-year-internationals', 'championship'
    ];
    const seasons = state.summary.seasons || [];
    state.leagueTableData = {};
    state.seasonPredictionData = {};
    for (const comp of competitions) {
        for (const season of seasons) {
            const leagueTableFile = `${dataDir}league_table_${comp}_${season}.json`;
            const seasonPredFile = `${dataDir}season_predicted_standings_${comp}_${season}.json`;
            state.leagueTableData[`${comp}_${season}`] = await loadJsonSafe(leagueTableFile, null);
            state.seasonPredictionData[`${comp}_${season}`] = await loadJsonSafe(seasonPredFile, null);
        }
    }
}

function populateLeagueTableSelects() {
    const compSelect = document.getElementById('league-table-competition');
    const seasonSelect = document.getElementById('league-table-season');
    if (!compSelect || !seasonSelect) return;
    const competitions = [...new Set(Object.keys(state.leagueTableData).map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];
    compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    // Set defaults
    state.selectedLeagueTableCompetition = competitions[0] || '';
    state.selectedLeagueTableSeason = seasons[seasons.length-1] || '';
}

function populateSeasonPredictionSelects() {
    const compSelect = document.getElementById('season-prediction-competition');
    const seasonSelect = document.getElementById('season-prediction-season');
    if (!compSelect || !seasonSelect) return;
    const competitions = [...new Set(Object.keys(state.seasonPredictionData).map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];
    compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    // Set defaults
    state.selectedSeasonPredictionCompetition = competitions[0] || '';
    state.selectedSeasonPredictionSeason = seasons[seasons.length-1] || '';
}
// ...existing code...

async function loadJsonSafe(url, fallback = null) {
    try {
        return await d3.json(url);
    } catch (error) {
        console.warn(`Missing or unreadable data file: ${url}`, error);
        return fallback;
    }
}

// Load all data
async function loadData() {
    // Load summary and all main data first
    try {
        const [summary, teamOffense, teamDefense, playerRankings, matchStats, teamStats,
            teamStrengthSeries, teamFinishPositions, upcomingPredictions, pathsToVictory, squadDepth] = await Promise.all([
            d3.json('data/summary.json'),
            d3.json('data/team_offense.json'),
            d3.json('data/team_defense.json'),
            d3.json('data/player_rankings.json'),
            d3.json('data/match_stats.json'),
            d3.json('data/team_stats.json'),
            loadJsonSafe('data/team_strength_series.json'),
            loadJsonSafe('data/team_finish_positions.json'),
            loadJsonSafe('data/upcoming_predictions.json'),
            loadJsonSafe('data/paths_to_victory.json'),
            loadJsonSafe('data/squad_depth.json')
        ]);

        state.summary = summary;
        state.teamOffense = teamOffense;
        state.teamDefense = teamDefense;
        state.playerRankings = playerRankings;
        state.matchStats = matchStats;
        state.teamStats = teamStats;
        state.teamStrengthSeries = teamStrengthSeries;
        state.teamFinishPositions = teamFinishPositions;
        state.upcomingPredictions = upcomingPredictions;
        state.pathsToVictory = pathsToVictory;
        state.squadDepth = squadDepth;

        // Now safe to load heatmap and other dependent data
        await loadHeatmapData();
        await loadLeagueTableAndSeasonPredictionData();

        // Set default season to most recent
        state.selectedSeason = summary.seasons[summary.seasons.length - 1];

        initializeDashboard();
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load dashboard data. Please ensure data files are generated.');
    }

    function populateLeagueTableSelects() {
        const compSelect = document.getElementById('league-table-competition');
        const seasonSelect = document.getElementById('league-table-season');
        if (!compSelect || !seasonSelect) return;
        const competitions = [...new Set(Object.keys(state.leagueTableData).map(k => k.split('_')[0]))];
        const seasons = state.summary.seasons || [];
        compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
        seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
        // Set defaults
        state.selectedLeagueTableCompetition = competitions[0] || '';
        state.selectedLeagueTableSeason = seasons[seasons.length-1] || '';
    }

    function populateSeasonPredictionSelects() {
        const compSelect = document.getElementById('season-prediction-competition');
        const seasonSelect = document.getElementById('season-prediction-season');
        if (!compSelect || !seasonSelect) return;
        const competitions = [...new Set(Object.keys(state.seasonPredictionData).map(k => k.split('_')[0]))];
        const seasons = state.summary.seasons || [];
        compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
        seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
        // Set defaults
        state.selectedSeasonPredictionCompetition = competitions[0] || '';
        state.selectedSeasonPredictionSeason = seasons[seasons.length-1] || '';
    }
    try {
        const [summary, teamOffense, teamDefense, playerRankings, matchStats, teamStats,
            teamStrengthSeries, teamFinishPositions, upcomingPredictions, pathsToVictory, squadDepth] = await Promise.all([
            d3.json('data/summary.json'),
            d3.json('data/team_offense.json'),
            d3.json('data/team_defense.json'),
            d3.json('data/player_rankings.json'),
            d3.json('data/match_stats.json'),
            d3.json('data/team_stats.json'),
            loadJsonSafe('data/team_strength_series.json'),
            loadJsonSafe('data/team_finish_positions.json'),
            loadJsonSafe('data/upcoming_predictions.json'),
            loadJsonSafe('data/paths_to_victory.json'),
            loadJsonSafe('data/squad_depth.json')
        ]);

        state.summary = summary;
        state.teamOffense = teamOffense;
        state.teamDefense = teamDefense;
        state.playerRankings = playerRankings;
        state.matchStats = matchStats;
        state.teamStats = teamStats;
        state.teamStrengthSeries = teamStrengthSeries;
        state.teamFinishPositions = teamFinishPositions;
        state.upcomingPredictions = upcomingPredictions;
        state.pathsToVictory = pathsToVictory;
        state.squadDepth = squadDepth;

        await loadLeagueTableAndSeasonPredictionData();

        // Set default season to most recent
        state.selectedSeason = summary.seasons[summary.seasons.length - 1];

        initializeDashboard();
    // Dynamically load all league table and season prediction files
    async function loadLeagueTableAndSeasonPredictionData() {
        const dataDir = 'data/';
        // List of files is static, but could be made dynamic with a manifest
        const competitions = [
            'six-nations', 'premiership', 'celtic', 'pro-d2', 'top14', 'euro-champions', 'euro-challenge',
            'mid-year-internationals', 'end-of-year-internationals', 'championship'
        ];
        const seasons = state.summary.seasons || [];
        state.leagueTableData = {};
        state.seasonPredictionData = {};
        for (const comp of competitions) {
            for (const season of seasons) {
                const leagueTableFile = `${dataDir}league_table_${comp}_${season}.json`;
                const seasonPredFile = `${dataDir}season_predicted_standings_${comp}_${season}.json`;
                state.leagueTableData[`${comp}_${season}`] = await loadJsonSafe(leagueTableFile, null);
                state.seasonPredictionData[`${comp}_${season}`] = await loadJsonSafe(seasonPredFile, null);
            }
        }
    }
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load dashboard data. Please ensure data files are generated.');
    }
}

// Initialize dashboard
function initializeDashboard() {
            populateHeatmapSelects();
        populateLeagueTableSelects();
        populateSeasonPredictionSelects();
    updateSummaryCards();
    populateGlobalControls();
    populateSeasonSelects();
    populateTeamSelect();
    populateTrendTeamSelect();
    populateFinishPositionSelects();
    populatePathsSelects();
    populateSquadSelects();
    updateAllVisualizations();
    setupEventListeners();
}

// Update summary cards
function updateSummaryCards() {
    document.getElementById('stat-seasons').textContent = state.summary.seasons.join(', ');
    document.getElementById('stat-matches').textContent = state.summary.total_matches.toLocaleString();
    document.getElementById('stat-teams').textContent = state.summary.total_teams;
    document.getElementById('stat-players').textContent = state.summary.total_players.toLocaleString();
    document.getElementById('last-updated').textContent = new Date(state.summary.generated_at).toLocaleString();
}

// Populate season dropdowns
function populateSeasonSelects() {
    const seasonSelect = document.getElementById('season-select');
    const matchSeasonSelect = document.getElementById('match-season');

    const options = state.summary.seasons.map(season =>
        `<option value="${season}" ${season === state.selectedSeason ? 'selected' : ''}>${season}</option>`
    ).join('');

    seasonSelect.innerHTML = options;
    matchSeasonSelect.innerHTML = options;
}

// Populate team filter
function populateTeamSelect() {
    const teamSelect = document.getElementById('match-team');
    const teams = [...new Set(state.matchStats.map(m => m.team))].sort();

    teamSelect.innerHTML = '<option value="">All Teams</option>' +
        teams.map(team => `<option value="${team}">${team}</option>`).join('');
}

// Populate global filter controls
function populateGlobalControls() {
    const globalComp = document.getElementById('global-competition');
    const globalSeason = document.getElementById('global-season');
    
    if (!globalComp || !globalSeason) return;
    
    // Get competitions from league table data (or could use summary.competitions)
    const competitions = [...new Set(Object.keys(state.leagueTableData).map(k => k.split('_')[0]))].sort();
    const seasons = state.summary.seasons || [];
    
    // Populate competition dropdown
    globalComp.innerHTML = '<option value="">All Competitions</option>' + 
        competitions.map(c => {
            const displayName = c.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            return `<option value="${c}">${displayName}</option>`;
        }).join('');
    
    // Populate season dropdown 
    globalSeason.innerHTML = '<option value="">All Seasons</option>' +
        seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    
    // Set defaults to most recent
    if (competitions.length > 0) {
        globalComp.value = competitions[0];
        state.selectedLeagueTableCompetition = competitions[0];
        state.selectedSeasonPredictionCompetition = competitions[0];
        state.selectedHeatmapCompetition = competitions[0];
    }
    
    if (seasons.length > 0) {
        const latestSeason = seasons[seasons.length - 1];
        globalSeason.value = latestSeason;
        state.selectedSeason = latestSeason;
        state.selectedLeagueTableSeason = latestSeason;
        state.selectedSeasonPredictionSeason = latestSeason;
        state.selectedHeatmapSeason = latestSeason;
    }
}

// Setup event listeners
function setupEventListeners() {
    // Global filter controls
    const applyFiltersBtn = document.getElementById('apply-filters');
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', () => {
            // Update global state from global controls
            const globalComp = document.getElementById('global-competition');
            const globalSeason = document.getElementById('global-season');
            const globalScoreType = document.getElementById('global-score-type');
            const globalRankLimit = document.getElementById('global-rank-limit');

            if (globalComp && globalComp.value) {
                state.selectedLeagueTableCompetition = globalComp.value;
                state.selectedSeasonPredictionCompetition = globalComp.value;
                state.selectedHeatmapCompetition = globalComp.value;
            }
            
            if (globalSeason && globalSeason.value) {
                state.selectedSeason = globalSeason.value;
                state.selectedLeagueTableSeason = globalSeason.value;
                state.selectedSeasonPredictionSeason = globalSeason.value;
                state.selectedHeatmapSeason = globalSeason.value;
            }
            
            if (globalScoreType) {
                state.selectedScoreType = globalScoreType.value;
            }
            
            if (globalRankLimit) {
                state.selectedRankLimit = parseInt(globalRankLimit.value);
            }

            // Update all visualizations with new global filters
            updateAllVisualizations();
            updateLeagueTable();
            updateSeasonPrediction();
            updateHeatmap();
        });
    }

    // Auto-populate global controls when filters change
    const globalComp = document.getElementById('global-competition');
    const globalSeason = document.getElementById('global-season');
    const globalScoreType = document.getElementById('global-score-type');
    const globalRankLimit = document.getElementById('global-rank-limit');
    
    if (globalComp) {
        globalComp.addEventListener('change', (e) => {
            state.selectedLeagueTableCompetition = e.target.value;
            state.selectedSeasonPredictionCompetition = e.target.value;
            state.selectedHeatmapCompetition = e.target.value;
        });
    }
    
    if (globalSeason) {
        globalSeason.addEventListener('change', (e) => {
            state.selectedSeason = e.target.value;
            state.selectedLeagueTableSeason = e.target.value;
            state.selectedSeasonPredictionSeason = e.target.value;
            state.selectedHeatmapSeason = e.target.value;
        });
    }
    
    if (globalScoreType) {
        globalScoreType.addEventListener('change', (e) => {
            state.selectedScoreType = e.target.value;
        });
    }
    
    if (globalRankLimit) {
        globalRankLimit.addEventListener('change', (e) => {
            state.selectedRankLimit = parseInt(e.target.value);
        });
    }

    // Individual control event listeners (only for controls that still exist in HTML)
    document.getElementById('season-select').addEventListener('change', (e) => {
        state.selectedSeason = e.target.value;
        updateAllVisualizations();
    });

    document.getElementById('score-type-select').addEventListener('change', (e) => {
        state.selectedScoreType = e.target.value;
        updateTeamVisualizations();
    });

    document.getElementById('rank-limit').addEventListener('change', (e) => {
        state.selectedRankLimit = parseInt(e.target.value);
        updateTeamVisualizations();
    });

    document.getElementById('player-score-type').addEventListener('change', (e) => {
        updatePlayerVisualizations(e.target.value);
    });

    document.getElementById('player-search').addEventListener('input', (e) => {
        filterPlayerTable(e.target.value);
    });

    document.getElementById('match-season').addEventListener('change', (e) => {
        updateMatchTable(e.target.value, document.getElementById('match-team').value);
    });

    document.getElementById('match-team').addEventListener('change', (e) => {
        updateMatchTable(document.getElementById('match-season').value, e.target.value);
    });

    const trendTeam = document.getElementById('trend-team');
    if (trendTeam) {
        trendTeam.addEventListener('change', updateTeamTrends);
    }
    const trendScore = document.getElementById('trend-score-type');
    if (trendScore) {
        trendScore.addEventListener('change', updateTeamTrends);
    }
    const trendMetric = document.getElementById('trend-metric');
    if (trendMetric) {
        trendMetric.addEventListener('change', updateTeamTrends);
    }

    const positionCompetition = document.getElementById('position-competition');
    if (positionCompetition) {
        positionCompetition.addEventListener('change', updateFinishPositions);
    }
    const positionSeason = document.getElementById('position-season');
    if (positionSeason) {
        positionSeason.addEventListener('change', updateFinishPositions);
    }

    const pathsCompetition = document.getElementById('paths-competition');
    if (pathsCompetition) {
        pathsCompetition.addEventListener('change', updatePathsToVictory);
    }
    const pathsTeam = document.getElementById('paths-team');
    if (pathsTeam) {
        pathsTeam.addEventListener('change', updatePathsToVictory);
    }

    const squadTeam = document.getElementById('squad-team');
    if (squadTeam) {
        squadTeam.addEventListener('change', updateSquadDepth);
    }
    const squadSeason = document.getElementById('squad-season');
    if (squadSeason) {
        squadSeason.addEventListener('change', updateSquadDepth);
    }
}

// Update all visualizations
function updateAllVisualizations() {
        updateHeatmap();
    updateTeamVisualizations();
    updatePlayerVisualizations('tries');
    updateMatchTable(state.selectedSeason, '');
    updateTeamTrends();
    // updateFinishPositions() is now called by populateFinishPositionSelects()
    updatePredictionTable();
    updatePathsToVictory();
    updateSquadDepth();
    updateLeagueTable();
    updateSeasonPrediction();

// Render league table
function populateLeagueTableSelects() {
    const compSelect = document.getElementById('league-table-competition');
    const seasonSelect = document.getElementById('league-table-season');
    if (!compSelect || !seasonSelect) return;
    const competitions = [...new Set(Object.keys(state.leagueTableData).map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];
    compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    // Set defaults
    state.selectedLeagueTableCompetition = competitions[0] || '';
    state.selectedLeagueTableSeason = seasons[seasons.length-1] || '';
}

function updateLeagueTable() {
    const tbody = document.querySelector('#league-table tbody');
    if (!tbody) return;
    const comp = state.selectedLeagueTableCompetition;
    const season = state.selectedLeagueTableSeason;
    if (!comp || !season) {
        tbody.innerHTML = '<tr><td colspan="14">Select competition and season.</td></tr>';
        return;
    }
    const key = `${comp}_${season}`;
    const data = state.leagueTableData[key];
    if (!data || !Array.isArray(data)) {
        tbody.innerHTML = '<tr><td colspan="14">No data available for this selection.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(row => `
        <tr>
            <td>${row.position}</td>
            <td><strong>${row.team}</strong></td>
            <td>${row.played}</td>
            <td>${row.won}</td>
            <td>${row.drawn}</td>
            <td>${row.lost}</td>
            <td>${row.points_for}</td>
            <td>${row.points_against}</td>
            <td>${row.points_diff}</td>
            <td>${row.tries_for}</td>
            <td>${row.tries_against}</td>
            <td>${row.bonus_points}</td>
            <td>${row.match_points}</td>
            <td>${row.total_points}</td>
        </tr>
    `).join('');
}

// Render season prediction
function populateSeasonPredictionSelects() {
    const compSelect = document.getElementById('season-prediction-competition');
    const seasonSelect = document.getElementById('season-prediction-season');
    if (!compSelect || !seasonSelect) return;
    const competitions = [...new Set(Object.keys(state.seasonPredictionData).map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];
    compSelect.innerHTML = '<option value="">Select...</option>' + competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' + seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    // Set defaults
    state.selectedSeasonPredictionCompetition = competitions[0] || '';
    state.selectedSeasonPredictionSeason = seasons[seasons.length-1] || '';
}

function updateSeasonPrediction() {
    const tbody = document.querySelector('#season-prediction-table tbody');
    if (!tbody) return;
    const comp = state.selectedSeasonPredictionCompetition;
    const season = state.selectedSeasonPredictionSeason;
    if (!comp || !season) {
        tbody.innerHTML = '<tr><td colspan="5">Select competition and season.</td></tr>';
        return;
    }
    const key = `${comp}_${season}`;
    const data = state.seasonPredictionData[key];
    if (!data || !Array.isArray(data)) {
        tbody.innerHTML = '<tr><td colspan="5">No data available for this selection.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(row => `
        <tr>
            <td><strong>${row.team}</strong></td>
            <td>${row.expected_points}</td>
            <td>${row.expected_wins}</td>
            <td>${row.expected_diff}</td>
            <td>${row.predicted_position}</td>
        </tr>
    `).join('');
}
}

function populateTrendTeamSelect() {
    if (!state.teamStrengthSeries) {
        return;
    }
    const teamSelect = document.getElementById('trend-team');
    if (!teamSelect) {
        return;
    }
    const teams = [...new Set(state.teamStrengthSeries.map(d => d.team))].sort();
    teamSelect.innerHTML = teams.map(team => `<option value="${team}">${team}</option>`).join('');
}

function populateFinishPositionSelects() {
    if (!state.teamFinishPositions) {
        return;
    }
    const competitionSelect = document.getElementById('position-competition');
    const seasonSelect = document.getElementById('position-season');
    if (!competitionSelect || !seasonSelect) {
        return;
    }
    const competitions = [...new Set(state.teamFinishPositions.map(d => d.competition))].sort();
    competitionSelect.innerHTML = competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    const seasons = [...new Set(state.teamFinishPositions.map(d => d.season))].sort().reverse();
    seasonSelect.innerHTML = '<option value="">All Seasons</option>' +
        seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    
    // Trigger initial update
    updateFinishPositions();
}

function populatePathsSelects() {
    if (!state.pathsToVictory) {
        return;
    }
    const competitionSelect = document.getElementById('paths-competition');
    const teamSelect = document.getElementById('paths-team');
    if (!competitionSelect || !teamSelect) {
        return;
    }
    const competitions = [...new Set(state.pathsToVictory.map(d => d.competition))].sort();
    competitionSelect.innerHTML = competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    const teams = [...new Set(state.pathsToVictory.map(d => d.team))].sort();
    teamSelect.innerHTML = teams.map(team => `<option value="${team}">${team}</option>`).join('');
}

function populateSquadSelects() {
    if (!state.squadDepth) {
        return;
    }
    const teamSelect = document.getElementById('squad-team');
    const seasonSelect = document.getElementById('squad-season');
    if (!teamSelect || !seasonSelect) {
        return;
    }
    const teams = [...new Set(state.squadDepth.map(d => d.team))].sort();
    teamSelect.innerHTML = teams.map(team => `<option value="${team}">${team}</option>`).join('');
    const seasons = [...new Set(state.squadDepth.map(d => d.season))].sort();
    seasonSelect.innerHTML = seasons.map(s => `<option value="${s}">${s}</option>`).join('');
}

function updateTeamTrends() {
    if (!state.teamStrengthSeries) {
        return;
    }
    const team = document.getElementById('trend-team')?.value;
    const scoreType = document.getElementById('trend-score-type')?.value || 'tries';
    const metric = document.getElementById('trend-metric')?.value || 'offense';
    if (!team) {
        return;
    }

    const key = metric === 'defense' ? 'defense_mean' : 'offense_mean';
    const filtered = state.teamStrengthSeries
        .filter(d => d.team === team && d.score_type === scoreType)
        .sort((a, b) => a.season.localeCompare(b.season));

    RugbyCharts.renderLineChart({
        container: '#trend-chart',
        data: filtered.map(d => ({ season: d.season, value: d[key] })),
        xKey: 'season',
        yKey: 'value',
        tooltipFormatter: d => `<strong>${team}</strong><br/>${d.season}: ${d.value.toFixed(3)}`,
    });
}

function updateFinishPositions() {
    if (!state.teamFinishPositions) {
        return;
    }
    const competition = document.getElementById('position-competition')?.value;
    const season = document.getElementById('position-season')?.value;
    if (!competition) {
        return;
    }

    let filtered = state.teamFinishPositions.filter(d => d.competition === competition);
    if (season) {
        filtered = filtered.filter(d => d.season === season);
    }

    // Group by team for multi-series visualization
    const teamData = {};
    filtered.forEach(d => {
        if (!teamData[d.team]) {
            teamData[d.team] = [];
        }
        teamData[d.team].push(d);
    });

    // Create data array with series for each team
    const data = [];
    Object.entries(teamData).forEach(([team, positions]) => {
        positions.sort((a, b) => a.season.localeCompare(b.season));
        positions.forEach(d => {
            data.push({
                team: team,
                season: d.season,
                position: d.position
            });
        });
    });

    RugbyCharts.renderMultiLineChart({
        container: '#position-chart',
        data: data,
        xKey: 'season',
        yKey: 'position',
        seriesKey: 'team',
        yReversed: true,
        yLabel: 'Position (lower is better)',
        xLabel: 'Season',
        tooltipFormatter: d => `<strong>${d.team}</strong><br/>${d.season}: #${d.position}`,
    });
}

function updatePredictionTable() {
    if (!state.upcomingPredictions) {
        return;
    }

    // No filtering - show all upcoming predictions
    const filtered = state.upcomingPredictions;

    filtered.sort((a, b) => new Date(a.date) - new Date(b.date));

    const tbody = document.querySelector('#prediction-table tbody');
    if (!tbody) {
        return;
    }
    tbody.innerHTML = filtered.slice(0, 50).map(d => {
        const date = new Date(d.date).toLocaleDateString();
        const winProb = Math.max(d.home_win_prob, d.away_win_prob);
        return `
            <tr>
                <td>${date}</td>
                <td><strong>${d.home_team}</strong></td>
                <td>${d.home_score_pred.toFixed(1)} - ${d.away_score_pred.toFixed(1)}</td>
                <td><strong>${d.away_team}</strong></td>
                <td>${(winProb * 100).toFixed(1)}%</td>
                <td><small>${d.competition}</small></td>
            </tr>
        `;
    }).join('');
}

function updatePathsToVictory() {
    if (!state.pathsToVictory) {
        return;
    }
    const competition = document.getElementById('paths-competition')?.value;
    const team = document.getElementById('paths-team')?.value;
    if (!competition || !team) {
        return;
    }

    const entry = state.pathsToVictory.find(
        d => d.competition === competition && d.team === team
    );

    const narrativeEl = document.getElementById('paths-narrative');
    const tbody = document.querySelector('#paths-critical-games tbody');

    if (!entry || !narrativeEl || !tbody) {
        return;
    }

    narrativeEl.textContent = entry.narrative || 'No narrative available.';
    tbody.innerHTML = entry.critical_games.map(game => `
        <tr>
            <td>${game.home_team} vs ${game.away_team}</td>
            <td>${game.mutual_information.toFixed(4)}</td>
        </tr>
    `).join('');
}

function updateSquadDepth() {
    if (!state.squadDepth) {
        return;
    }
    const team = document.getElementById('squad-team')?.value;
    const season = document.getElementById('squad-season')?.value;
    if (!team || !season) {
        return;
    }

    const entry = state.squadDepth.find(d => d.team === team && d.season === season);
    const summaryEl = document.getElementById('squad-summary');
    const tbody = document.querySelector('#squad-table tbody');

    if (!entry || !summaryEl || !tbody) {
        return;
    }

    summaryEl.textContent = `Overall strength: ${(entry.overall_strength * 100).toFixed(0)}/100 · Depth score: ${(entry.depth_score * 100).toFixed(0)}/100`;

    tbody.innerHTML = entry.positions.map(pos => {
        const players = pos.players.map(p => `${p.player} (${p.rating.toFixed(2)})`).join(', ');
        return `
            <tr>
                <td><strong>${pos.position}</strong></td>
                <td>${players}</td>
                <td>${(pos.expected_strength * 100).toFixed(0)}</td>
                <td>${(pos.depth_score * 100).toFixed(0)}</td>
            </tr>
        `;
    }).join('');
}

// Update team visualizations
function updateTeamVisualizations() {
    const offenseData = filterTeamData(state.teamOffense, state.selectedSeason, state.selectedScoreType);
    const defenseData = filterTeamData(state.teamDefense, state.selectedSeason, state.selectedScoreType);

    drawOffenseChart(offenseData.slice(0, state.selectedRankLimit));
    drawDefenseChart(defenseData.slice(0, state.selectedRankLimit));
    drawComparisonChart(offenseData, defenseData);
    updateOffenseTable(offenseData.slice(0, state.selectedRankLimit));
    updateDefenseTable(defenseData.slice(0, state.selectedRankLimit));
}

// Filter team data
function filterTeamData(data, season, scoreType) {
    return data
        .filter(d => d.season === season && d.score_type === scoreType)
        .sort((a, b) => {
            const meanA = a.offense_mean !== undefined ? a.offense_mean : a.defense_mean;
            const meanB = b.offense_mean !== undefined ? b.offense_mean : b.defense_mean;
            return meanB - meanA;
        });
}

// Draw offensive chart
function drawOffenseChart(data) {
    RugbyCharts.renderBarChartWithCI({
        container: '#offense-chart',
        data,
        labelKey: 'team',
        meanKey: 'offense_mean',
        lowerKey: 'offense_lower',
        upperKey: 'offense_upper',
        color: '#0d6efd',
        tooltipFormatter: d => `<strong>${d.team}</strong><br/>
            Effect: ${d.offense_mean.toFixed(3)}<br/>
            95% CI: [${d.offense_lower.toFixed(3)}, ${d.offense_upper.toFixed(3)}]`,
    });
}

// Draw defensive chart
function drawDefenseChart(data) {
    RugbyCharts.renderBarChartWithCI({
        container: '#defense-chart',
        data,
        labelKey: 'team',
        meanKey: 'defense_mean',
        lowerKey: 'defense_lower',
        upperKey: 'defense_upper',
        color: '#198754',
        tooltipFormatter: d => `<strong>${d.team}</strong><br/>
            Effect: ${d.defense_mean.toFixed(3)}<br/>
            95% CI: [${d.defense_lower.toFixed(3)}, ${d.defense_upper.toFixed(3)}]`,
    });
}

// Draw comparison chart (offense vs defense)
function drawComparisonChart(offenseData, defenseData) {
    const combinedData = offenseData.map(o => {
        const d = defenseData.find(d => d.team === o.team);
        return d ? {
            team: o.team,
            offense: o.offense_mean,
            defense: d.defense_mean
        } : null;
    }).filter(d => d !== null);

    RugbyCharts.renderScatterPlot({
        container: '#comparison-chart',
        data: combinedData,
        xKey: 'offense',
        yKey: 'defense',
        labelKey: 'team',
        tooltipFormatter: d => `<strong>${d.team}</strong><br/>
            Offense: ${d.offense.toFixed(3)}<br/>
            Defense: ${d.defense.toFixed(3)}`,
    });
}

// Update offense table
function updateOffenseTable(data) {
    const tbody = document.querySelector('#offense-table tbody');
    tbody.innerHTML = data.map((d, i) => {
        const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : 'default';
        const uncertainty = d.offense_std;
        const uncertaintyClass = uncertainty < 0.05 ? 'low' : uncertainty < 0.1 ? 'medium' : 'high';
        const uncertaintyLabel = uncertainty < 0.05 ? 'Low' : uncertainty < 0.1 ? 'Med' : 'High';

        return `
            <tr>
                <td><span class="rank-badge ${rankClass}">${i + 1}</span></td>
                <td><strong>${d.team}</strong></td>
                <td>${d.offense_mean.toFixed(3)}</td>
                <td><span class="uncertainty-badge ${uncertaintyClass}">${uncertaintyLabel}</span></td>
            </tr>
        `;
    }).join('');
}

// Update defense table
function updateDefenseTable(data) {
    const tbody = document.querySelector('#defense-table tbody');
    tbody.innerHTML = data.map((d, i) => {
        const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : 'default';
        const uncertainty = d.defense_std;
        const uncertaintyClass = uncertainty < 0.05 ? 'low' : uncertainty < 0.1 ? 'medium' : 'high';
        const uncertaintyLabel = uncertainty < 0.05 ? 'Low' : uncertainty < 0.1 ? 'Med' : 'High';

        return `
            <tr>
                <td><span class="rank-badge ${rankClass}">${i + 1}</span></td>
                <td><strong>${d.team}</strong></td>
                <td>${d.defense_mean.toFixed(3)}</td>
                <td><span class="uncertainty-badge ${uncertaintyClass}">${uncertaintyLabel}</span></td>
            </tr>
        `;
    }).join('');
}

// Update player visualizations
function updatePlayerVisualizations(scoreType) {
    const data = state.playerRankings
        .filter(d => d.score_type === scoreType)
        .sort((a, b) => b.effect_mean - a.effect_mean)
        .slice(0, 20);

    drawPlayerChart(data);
    updatePlayerTable(data);
}

// Draw player chart
function drawPlayerChart(data) {
    RugbyCharts.renderBarChartWithCI({
        container: '#player-chart',
        data,
        labelKey: 'player',
        meanKey: 'effect_mean',
        lowerKey: 'effect_lower',
        upperKey: 'effect_upper',
        color: '#6f42c1',
    });
}

// Update player table
function updatePlayerTable(data) {
    const tbody = document.querySelector('#player-table tbody');
    tbody.innerHTML = data.map((d, i) => `
        <tr>
            <td>${i + 1}</td>
            <td><strong>${d.player}</strong></td>
            <td>${d.effect_mean.toFixed(3)}</td>
            <td>${d.effect_lower.toFixed(3)} – ${d.effect_upper.toFixed(3)}</td>
        </tr>
    `).join('');
}

// Filter player table
function filterPlayerTable(searchTerm) {
    const scoreType = document.getElementById('player-score-type').value;
    const data = state.playerRankings
        .filter(d => d.score_type === scoreType)
        .sort((a, b) => b.effect_mean - a.effect_mean);

    const filtered = searchTerm
        ? data.filter(d => d.player.toLowerCase().includes(searchTerm.toLowerCase()))
        : data.slice(0, 20);

    updatePlayerTable(filtered.slice(0, 50));
}

// Update match table
function updateMatchTable(season, team) {
    let filtered = state.matchStats.filter(d => d.season === season);

    if (team) {
        filtered = filtered.filter(d => d.team === team || d.opponent === team);
    }

    filtered.sort((a, b) => new Date(b.date) - new Date(a.date));

    const tbody = document.querySelector('#match-table tbody');
    tbody.innerHTML = filtered.slice(0, 100).map(d => {
        const date = new Date(d.date).toLocaleDateString();
        const homeWin = d.team_score > d.opponent_score;
        const resultClass = homeWin ? 'text-success' : 'text-danger';

        return `
            <tr>
                <td>${date}</td>
                <td><strong>${d.team}</strong></td>
                <td class="${resultClass}"><strong>${d.team_score} - ${d.opponent_score}</strong></td>
                <td><strong>${d.opponent}</strong></td>
                <td><small>${d.competition}</small></td>
            </tr>
        `;
    }).join('');
}

// Tooltip functions
function showTooltip(event, content) {
    let tooltip = document.querySelector('.tooltip-d3');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'tooltip-d3';
        document.body.appendChild(tooltip);
    }

    tooltip.innerHTML = content;
    tooltip.style.display = 'block';
    tooltip.style.left = (event.pageX + 10) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';
}

function hideTooltip() {
    const tooltip = document.querySelector('.tooltip-d3');
    if (tooltip) {
        tooltip.style.display = 'none';
    }
}

// Error display
function showError(message) {
    const container = document.querySelector('.container-fluid');
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.role = 'alert';
    alert.innerHTML = `
        <strong>Error!</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.insertBefore(alert, container.firstChild);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadData();
});
