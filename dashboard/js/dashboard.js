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
    bracketData: {},
    selectedCompetition: null,  // Global competition filter
    selectedLeagueTableCompetition: null,
    selectedLeagueTableSeason: null,
    selectedSeasonPredictionCompetition: null,
    selectedSeasonPredictionSeason: null,
    selectedHeatmapCompetition: null,
    selectedHeatmapSeason: null,
    selectedBracketCompetition: null,
    selectedBracketSeason: null,
    selectedSeason: null,
    selectedScoreType: 'tries',
    selectedRankLimit: 20
};

// Track which sections have been loaded
const loadedSections = {
    core: false,
    teams: false,
    players: false,
    trends: false,
    positions: false,
    matches: false,
    predictions: false,
    paths: false,
    squads: false,
    heatmaps: false,
    leagueTables: false,
    bracket: false
};

// Heatmap rendering with D3
function renderHeatmap(data, teams, container) {
    const el = document.querySelector(container);
    if (!el) return;

    // Clear existing content
    el.innerHTML = '';

    if (!data || !teams || teams.length === 0) {
        el.innerHTML = '<div class="text-muted text-center py-5">No heatmap data available</div>';
        return;
    }

    // Set dimensions
    const margin = {top: 100, right: 50, bottom: 50, left: 100};
    const cellSize = 40;
    const width = cellSize * teams.length + margin.left + margin.right;
    const height = cellSize * teams.length + margin.top + margin.bottom;

    // Create SVG
    const svg = d3.select(el)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Create color scale (lighter = better for team, darker = worse)
    const colorScale = d3.scaleSequential(d3.interpolateRdYlGn)
        .domain([-40, 40]); // Adjust based on your data range

    // Draw cells
    for (let i = 0; i < teams.length; i++) {
        for (let j = 0; j < teams.length; j++) {
            const value = data[i][j];
            if (value !== null && value !== undefined) {
                g.append('rect')
                    .attr('x', j * cellSize)
                    .attr('y', i * cellSize)
                    .attr('width', cellSize)
                    .attr('height', cellSize)
                    .attr('fill', colorScale(value))
                    .attr('stroke', '#fff')
                    .attr('stroke-width', 1)
                    .append('title')
                    .text(`${teams[i]} vs ${teams[j]}: ${value !== null ? value.toFixed(1) : 'N/A'}`);
            }
        }
    }

    // Add row labels (teams on Y-axis)
    g.selectAll('.row-label')
        .data(teams)
        .enter()
        .append('text')
        .attr('x', -5)
        .attr('y', (d, i) => i * cellSize + cellSize / 2)
        .attr('dy', '.35em')
        .attr('text-anchor', 'end')
        .attr('font-size', '10px')
        .text(d => d);

    // Add column labels (teams on X-axis)
    g.selectAll('.col-label')
        .data(teams)
        .enter()
        .append('text')
        .attr('x', (d, i) => i * cellSize + cellSize / 2)
        .attr('y', -5)
        .attr('text-anchor', 'start')
        .attr('transform', (d, i) => `rotate(-45, ${i * cellSize + cellSize / 2}, -5)`)
        .attr('font-size', '10px')
        .text(d => d);
}

// Lazy load heatmap data (only for existing files)
async function loadHeatmapData() {
    if (loadedSections.heatmaps) return;

    showSectionLoader('heatmaps-section');

    try {
        const dataDir = 'data/';
        // Only load heatmaps for competitions that exist in summary
        const competitions = state.summary.competitions || ['rugby-world'];
        const seasons = state.summary.seasons || [];

        state.heatmapData = {};
        for (const comp of competitions) {
            for (const season of seasons) {
                const file = `${dataDir}team_heatmap_${comp}_${season}.json`;
                const data = await loadJsonSafe(file, null);
                if (data) {  // Only store if file exists
                    state.heatmapData[`${comp}_${season}`] = data;
                }
            }
        }

        loadedSections.heatmaps = true;
    } catch (error) {
        console.error('Error loading heatmap data:', error);
    } finally {
        hideSectionLoader('heatmaps-section');
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
// Lazy load league table and season prediction data (only for existing files)
async function loadLeagueTableAndSeasonPredictionData() {
    if (loadedSections.leagueTables) return;

    showSectionLoader('league-tables-section');

    try {
        const dataDir = 'data/';
        // Only load for competitions that exist in summary
        const competitions = state.summary.competitions || ['rugby-world'];
        const seasons = state.summary.seasons || [];

        state.leagueTableData = {};
        state.seasonPredictionData = {};

        for (const comp of competitions) {
            for (const season of seasons) {
                const leagueTableFile = `${dataDir}league_table_${comp}_${season}.json`;
                const seasonPredFile = `${dataDir}season_predicted_standings_${comp}_${season}.json`;

                const leagueData = await loadJsonSafe(leagueTableFile, null);
                const predData = await loadJsonSafe(seasonPredFile, null);

                // Only store if files exist
                if (leagueData) {
                    state.leagueTableData[`${comp}_${season}`] = leagueData;
                }
                if (predData) {
                    state.seasonPredictionData[`${comp}_${season}`] = predData;
                }
            }
        }

        loadedSections.leagueTables = true;
    } catch (error) {
        console.error('Error loading league table data:', error);
    } finally {
        hideSectionLoader('league-tables-section');
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

// Show loading spinner in a section
function showSectionLoader(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;

    const existingLoader = section.querySelector('.section-loader');
    if (existingLoader) return; // Already showing

    const loader = document.createElement('div');
    loader.className = 'section-loader text-center py-5';
    loader.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        <p class="text-muted mt-2">Loading data...</p>
    `;
    section.insertBefore(loader, section.firstChild);
}

// Hide loading spinner
function hideSectionLoader(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;

    const loader = section.querySelector('.section-loader');
    if (loader) {
        loader.remove();
    }
}

// Load initial data (only summary)
async function loadData() {
    try {
        const summary = await d3.json('data/summary.json');
        state.summary = summary;

        // Set default season to most recent
        state.selectedSeason = summary.seasons[summary.seasons.length - 1];

        loadedSections.core = true;

        initializeDashboard();
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load dashboard data. Please ensure data files are generated.');
    }
}

// Lazy load core team and player data (for Overview, Teams, Players sections)
async function loadCoreData() {
    if (loadedSections.teams && loadedSections.players) return;

    try {
        const [teamOffense, teamDefense, playerRankings] = await Promise.all([
            d3.json('data/team_offense.json'),
            d3.json('data/team_defense.json'),
            d3.json('data/player_rankings.json')
        ]);

        state.teamOffense = teamOffense;
        state.teamDefense = teamDefense;
        state.playerRankings = playerRankings;

        loadedSections.teams = true;
        loadedSections.players = true;
    } catch (error) {
        console.error('Error loading core data:', error);
        throw error;
    }
}

// Lazy load trends data
async function loadTrendsData() {
    if (loadedSections.trends) return;

    showSectionLoader('trends');

    try {
        const teamStrengthSeries = await loadJsonSafe('data/team_strength_series.json');
        state.teamStrengthSeries = teamStrengthSeries;
        loadedSections.trends = true;
    } catch (error) {
        console.error('Error loading trends data:', error);
    } finally {
        hideSectionLoader('trends');
    }
}

// Lazy load positions data
async function loadPositionsData() {
    if (loadedSections.positions) return;

    showSectionLoader('positions');

    try {
        const teamFinishPositions = await loadJsonSafe('data/team_finish_positions.json');
        state.teamFinishPositions = teamFinishPositions;
        loadedSections.positions = true;
    } catch (error) {
        console.error('Error loading positions data:', error);
    } finally {
        hideSectionLoader('positions');
    }
}

// Lazy load matches data
async function loadMatchesData() {
    if (loadedSections.matches) return;

    showSectionLoader('matches');

    try {
        const [matchStats, teamStats] = await Promise.all([
            d3.json('data/match_stats.json'),
            d3.json('data/team_stats.json')
        ]);

        state.matchStats = matchStats;
        state.teamStats = teamStats;
        loadedSections.matches = true;
    } catch (error) {
        console.error('Error loading matches data:', error);
    } finally {
        hideSectionLoader('matches');
    }
}

// Lazy load predictions data
async function loadPredictionsData() {
    if (loadedSections.predictions) return;

    showSectionLoader('predictions');

    try {
        const upcomingPredictions = await loadJsonSafe('data/upcoming_predictions.json');
        state.upcomingPredictions = upcomingPredictions;
        loadedSections.predictions = true;
    } catch (error) {
        console.error('Error loading predictions data:', error);
    } finally {
        hideSectionLoader('predictions');
    }
}

// Lazy load paths to victory data
async function loadPathsData() {
    if (loadedSections.paths) return;

    showSectionLoader('paths');

    try {
        const pathsToVictory = await loadJsonSafe('data/paths_to_victory.json');
        state.pathsToVictory = pathsToVictory;
        loadedSections.paths = true;
    } catch (error) {
        console.error('Error loading paths data:', error);
    } finally {
        hideSectionLoader('paths');
    }
}

// Lazy load squad depth data
async function loadSquadsData() {
    if (loadedSections.squads) return;

    showSectionLoader('squads');

    try {
        const squadDepth = await loadJsonSafe('data/squad_depth.json');
        state.squadDepth = squadDepth;
        loadedSections.squads = true;
    } catch (error) {
        console.error('Error loading squads data:', error);
    } finally {
        hideSectionLoader('squads');
    }
}

// Initialize dashboard
function initializeDashboard() {
    // Only initialize summary cards and basic controls
    updateSummaryCards();
    setupEventListeners();
    setupNavigationHandlers();

    // Load core data for overview section
    loadCoreData().then(() => {
        populateGlobalControls();
        updateAllVisualizations();  // Show initial overview data
    });
}

// Setup navigation handlers for lazy loading
function setupNavigationHandlers() {
    // Handle hash changes for section navigation
    window.addEventListener('hashchange', handleSectionNavigation);

    // Handle initial hash on page load
    if (window.location.hash) {
        handleSectionNavigation();
    }

    // Also add click handlers to nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            // Let default navigation happen, hashchange will trigger loading
        });
    });
}

// Handle section navigation and lazy load data
async function handleSectionNavigation() {
    const hash = window.location.hash.slice(1); // Remove the #

    switch (hash) {
        case 'overview':
        case 'teams':
            await loadCoreData();
            populateSeasonSelects();
            populateTeamSelect();
            updateAllVisualizations();
            break;

        case 'players':
            await loadCoreData();
            updatePlayerRankings();
            break;

        case 'trends':
            await loadTrendsData();
            populateTrendTeamSelect();
            updateTrendChart();
            break;

        case 'positions':
            await loadPositionsData();
            populateFinishPositionSelects();
            updateFinishPositionChart();
            break;

        case 'matches':
            await loadMatchesData();
            updateMatchStats();
            break;

        case 'predictions':
            await loadPredictionsData();
            updatePredictions();
            break;

        case 'paths':
            await loadPathsData();
            populatePathsSelects();
            updatePathsToVictory();
            break;

        case 'squads':
            await loadSquadsData();
            populateSquadSelects();
            updateSquadDepth();
            break;

        case 'bracket':
            await loadBracketData();
            populateBracketSelects();
            updateBracket();
            break;

        default:
            // Default to overview
            await loadCoreData();
            updateAllVisualizations();
            break;
    }
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

// Lazy load bracket data
async function loadBracketData() {
    if (loadedSections.bracket) return;

    showSectionLoader('bracket');

    try {
        const dataDir = 'data/';
        const competitions = state.summary.competitions || [];
        const seasons = state.summary.seasons || [];

        state.bracketData = {};

        for (const comp of competitions) {
            for (const season of seasons) {
                const file = `${dataDir}knockout_bracket_${comp}_${season}.json`;
                const data = await loadJsonSafe(file, null);
                if (data && data.matches && data.matches.length > 0) {
                    state.bracketData[`${comp}_${season}`] = data;
                }
            }
        }

        loadedSections.bracket = true;
    } catch (error) {
        console.error('Error loading bracket data:', error);
    } finally {
        hideSectionLoader('bracket');
    }
}

function populateBracketSelects() {
    const compSelect = document.getElementById('bracket-competition');
    const seasonSelect = document.getElementById('bracket-season');
    if (!compSelect || !seasonSelect) return;

    const keys = Object.keys(state.bracketData);
    if (keys.length === 0) {
        compSelect.innerHTML = '<option value="">No knockout tournaments available</option>';
        seasonSelect.innerHTML = '<option value="">No data</option>';
        return;
    }

    const competitions = [...new Set(keys.map(k => k.split('_')[0]))];
    const seasons = state.summary.seasons || [];

    compSelect.innerHTML = '<option value="">Select...</option>' +
        competitions.map(c => `<option value="${c}">${c}</option>`).join('');
    seasonSelect.innerHTML = '<option value="">Select...</option>' +
        seasons.map(s => `<option value="${s}">${s}</option>`).join('');

    // Set defaults to first available
    state.selectedBracketCompetition = competitions[0] || '';
    state.selectedBracketSeason = seasons[seasons.length - 1] || '';

    compSelect.value = state.selectedBracketCompetition;
    seasonSelect.value = state.selectedBracketSeason;

    // Add event listeners
    compSelect.addEventListener('change', (e) => {
        state.selectedBracketCompetition = e.target.value;
        updateBracket();
    });

    seasonSelect.addEventListener('change', (e) => {
        state.selectedBracketSeason = e.target.value;
        updateBracket();
    });
}

function updateBracket() {
    const container = document.getElementById('bracket-container');
    if (!container) return;

    const comp = state.selectedBracketCompetition;
    const season = state.selectedBracketSeason;

    if (!comp || !season) {
        container.innerHTML = '<div class="text-muted text-center py-5">Select competition and season</div>';
        return;
    }

    const key = `${comp}_${season}`;
    const bracketData = state.bracketData[key];

    if (!bracketData || !bracketData.matches || bracketData.matches.length === 0) {
        container.innerHTML = '<div class="text-muted text-center py-5">No knockout fixtures for this selection</div>';
        return;
    }

    // Render bracket as a list for now (can enhance with visual bracket later)
    let html = '';

    if (bracketData.note) {
        html += `<div class="alert alert-info mb-3">${bracketData.note}</div>`;
    }

    // Group matches by round
    const byRound = {};
    for (const match of bracketData.matches) {
        const roundType = match.round_type || 'knockout';
        if (!byRound[roundType]) {
            byRound[roundType] = [];
        }
        byRound[roundType].push(match);
    }

    // Render each round
    const roundOrder = ['round_of_16', 'quarterfinal', 'semifinal', 'third_place', 'final'];
    const roundNames = {
        'round_of_16': 'Round of 16',
        'quarterfinal': 'Quarterfinals',
        'semifinal': 'Semifinals',
        'third_place': 'Third Place',
        'final': 'Final',
        'knockout': 'Knockout'
    };

    for (const round of roundOrder) {
        if (byRound[round]) {
            html += `<h5 class="mt-4 mb-3">${roundNames[round] || round}</h5>`;
            html += '<div class="row g-3">';

            for (const match of byRound[round]) {
                const isTBC = match.home_team.includes('TBC') || match.away_team.includes('TBC');
                const cardClass = isTBC ? 'border-warning' : 'border-primary';
                const dateStr = match.date ? new Date(match.date).toLocaleDateString() : 'TBD';

                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card ${cardClass} h-100">
                            <div class="card-body">
                                <div class="text-center">
                                    <strong>${match.home_team}</strong>
                                    <div class="text-muted my-2">vs</div>
                                    <strong>${match.away_team}</strong>
                                </div>
                                <div class="text-muted text-center mt-2 small">
                                    ${dateStr}
                                    ${match.stadium ? `<br>${match.stadium}` : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            html += '</div>';
        }
    }

    // Handle any other rounds not in the standard order
    for (const round in byRound) {
        if (!roundOrder.includes(round)) {
            html += `<h5 class="mt-4 mb-3">${roundNames[round] || round}</h5>`;
            html += '<div class="row g-3">';

            for (const match of byRound[round]) {
                const isTBC = match.home_team.includes('TBC') || match.away_team.includes('TBC');
                const cardClass = isTBC ? 'border-warning' : 'border-primary';
                const dateStr = match.date ? new Date(match.date).toLocaleDateString() : 'TBD';

                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card ${cardClass} h-100">
                            <div class="card-body">
                                <div class="text-center">
                                    <strong>${match.home_team}</strong>
                                    <div class="text-muted my-2">vs</div>
                                    <strong>${match.away_team}</strong>
                                </div>
                                <div class="text-muted text-center mt-2 small">
                                    ${dateStr}
                                    ${match.stadium ? `<br>${match.stadium}` : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            html += '</div>';
        }
    }

    container.innerHTML = html;
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

            if (globalComp) {
                state.selectedCompetition = globalComp.value || null;
                state.selectedLeagueTableCompetition = globalComp.value;
                state.selectedSeasonPredictionCompetition = globalComp.value;
                state.selectedHeatmapCompetition = globalComp.value;
            }

            if (globalSeason) {
                state.selectedSeason = globalSeason.value || null;
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
            updateFinishPositionChart();
            updateTrendChart();
        });
    }

    // Auto-populate global controls when filters change
    const globalComp = document.getElementById('global-competition');
    const globalSeason = document.getElementById('global-season');
    const globalScoreType = document.getElementById('global-score-type');
    const globalRankLimit = document.getElementById('global-rank-limit');

    if (globalComp) {
        globalComp.addEventListener('change', (e) => {
            state.selectedCompetition = e.target.value || null;
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

    // Individual control event listeners removed - now using global controls only

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
        trendTeam.addEventListener('change', updateTrendChart);
    }
    const trendMetric = document.getElementById('trend-metric');
    if (trendMetric) {
        trendMetric.addEventListener('change', updateTrendChart);
    }

    // Position chart now uses global controls - no local listeners needed

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
    // This function is no longer needed as we use global controls
    // Just trigger the update using current global state
    updateFinishPositionChart();
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

function updateTrendChart() {
    if (!state.teamStrengthSeries) {
        return;
    }
    const team = document.getElementById('trend-team')?.value;
    const scoreType = state.selectedScoreType || 'tries';  // Use global score type
    const metric = document.getElementById('trend-metric')?.value || 'offense';
    if (!team) {
        const container = document.querySelector('#trend-chart');
        if (container) {
            container.innerHTML = '<div class="text-muted text-center py-5">Please select a team</div>';
        }
        return;
    }

    const key = metric === 'defense' ? 'defense_mean' : 'offense_mean';
    const filtered = state.teamStrengthSeries
        .filter(d => d.team === team && d.score_type === scoreType)
        .sort((a, b) => a.season.localeCompare(b.season));

    if (filtered.length === 0) {
        const container = document.querySelector('#trend-chart');
        if (container) {
            container.innerHTML = '<div class="text-muted text-center py-5">No data available for selected team and filters</div>';
        }
        return;
    }

    RugbyCharts.renderLineChart({
        container: '#trend-chart',
        data: filtered.map(d => ({ season: d.season, value: d[key] })),
        xKey: 'season',
        yKey: 'value',
        yLabel: metric === 'defense' ? 'Defensive Strength' : 'Offensive Strength',
        tooltipFormatter: d => `<strong>${team}</strong><br/>${d.season}: ${d.value.toFixed(3)}`,
    });
}

function updateFinishPositionChart() {
    if (!state.teamFinishPositions) {
        return;
    }

    // Use global competition and season filters
    const competition = state.selectedCompetition;
    const season = state.selectedSeason;

    // Filter by competition if selected
    let filtered = state.teamFinishPositions;
    if (competition) {
        filtered = filtered.filter(d => d.competition === competition);
    }

    // Filter by season if selected
    if (season) {
        filtered = filtered.filter(d => d.season === season);
    }

    // If no data, show message
    if (filtered.length === 0) {
        const container = document.querySelector('#position-chart');
        if (container) {
            container.innerHTML = '<div class="text-muted text-center py-5">No finish position data available for selected filters</div>';
        }
        return;
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
