// Reusable D3 chart toolkit for rugby dashboards and embeds
(function (global) {
    'use strict';

    function resolveContainer(container) {
        if (typeof container === 'string') {
            return document.querySelector(container);
        }
        return container;
    }

    function clearContainer(container) {
        const el = resolveContainer(container);
        if (el) {
            el.innerHTML = '';
        }
        return el;
    }

    function ensureTooltip() {
        let tooltip = document.querySelector('.tooltip-d3');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.className = 'tooltip-d3';
            document.body.appendChild(tooltip);
        }
        return tooltip;
    }

    function showTooltip(event, content) {
        const tooltip = ensureTooltip();
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

    function renderBarChartWithCI(options) {
        const {
            container,
            data,
            labelKey,
            meanKey,
            lowerKey,
            upperKey,
            color = '#0d6efd',
            height = 400,
            margin = { top: 20, right: 30, bottom: 60, left: 150 },
            tooltipFormatter,
        } = options;

        const el = clearContainer(container);
        if (!el) {
            return;
        }

        const width = el.clientWidth - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = d3.select(el)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', innerHeight + margin.top + margin.bottom)
            .append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear()
            .domain([
                d3.min(data, d => d[lowerKey]) * 1.1,
                d3.max(data, d => d[upperKey]) * 1.1
            ])
            .range([0, width]);

        const y = d3.scaleBand()
            .domain(data.map(d => d[labelKey]))
            .range([0, innerHeight])
            .padding(0.2);

        svg.append('g')
            .attr('transform', `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x).ticks(5))
            .attr('class', 'axis');

        svg.append('g')
            .call(d3.axisLeft(y))
            .attr('class', 'axis');

        svg.selectAll('.error-bar')
            .data(data)
            .enter()
            .append('line')
            .attr('class', 'error-bar')
            .attr('x1', d => x(d[lowerKey]))
            .attr('x2', d => x(d[upperKey]))
            .attr('y1', d => y(d[labelKey]) + y.bandwidth() / 2)
            .attr('y2', d => y(d[labelKey]) + y.bandwidth() / 2);

        svg.selectAll('.bar')
            .data(data)
            .enter()
            .append('rect')
            .attr('class', 'bar')
            .attr('x', x(0))
            .attr('y', d => y(d[labelKey]))
            .attr('width', d => x(d[meanKey]) - x(0))
            .attr('height', y.bandwidth())
            .attr('fill', color)
            .attr('opacity', 0.8)
            .on('mouseover', function (event, d) {
                d3.select(this).attr('opacity', 1);
                if (tooltipFormatter) {
                    showTooltip(event, tooltipFormatter(d));
                }
            })
            .on('mouseout', function () {
                d3.select(this).attr('opacity', 0.8);
                hideTooltip();
            });

        svg.append('g')
            .attr('class', 'grid')
            .call(d3.axisBottom(x).tickSize(innerHeight).tickFormat(''))
            .selectAll('line')
            .attr('stroke', '#e9ecef');
    }

    function renderScatterPlot(options) {
        const {
            container,
            data,
            xKey,
            yKey,
            labelKey,
            height = 500,
            margin = { top: 40, right: 40, bottom: 60, left: 60 },
            tooltipFormatter,
        } = options;

        const el = clearContainer(container);
        if (!el) {
            return;
        }

        const width = el.clientWidth - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = d3.select(el)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', innerHeight + margin.top + margin.bottom)
            .append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear()
            .domain(d3.extent(data, d => d[xKey]))
            .nice()
            .range([0, width]);

        const y = d3.scaleLinear()
            .domain(d3.extent(data, d => d[yKey]))
            .nice()
            .range([innerHeight, 0]);

        const color = d3.scaleOrdinal(d3.schemeCategory10);

        svg.append('g')
            .attr('class', 'grid')
            .attr('transform', `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x).tickSize(-innerHeight).tickFormat(''));

        svg.append('g')
            .attr('class', 'grid')
            .call(d3.axisLeft(y).tickSize(-width).tickFormat(''));

        svg.append('g')
            .attr('transform', `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x))
            .attr('class', 'axis');

        svg.append('g')
            .call(d3.axisLeft(y))
            .attr('class', 'axis');

        svg.append('line')
            .attr('x1', x(0))
            .attr('x2', x(0))
            .attr('y1', 0)
            .attr('y2', innerHeight)
            .attr('stroke', '#adb5bd')
            .attr('stroke-dasharray', '5,5');

        svg.append('line')
            .attr('x1', 0)
            .attr('x2', width)
            .attr('y1', y(0))
            .attr('y2', y(0))
            .attr('stroke', '#adb5bd')
            .attr('stroke-dasharray', '5,5');

        svg.selectAll('.scatter-point')
            .data(data)
            .enter()
            .append('circle')
            .attr('class', 'scatter-point')
            .attr('cx', d => x(d[xKey]))
            .attr('cy', d => y(d[yKey]))
            .attr('r', 5)
            .attr('fill', d => color(d[labelKey]))
            .attr('opacity', 0.7)
            .on('mouseover', function (event, d) {
                d3.select(this).attr('r', 7).attr('opacity', 1);
                if (tooltipFormatter) {
                    showTooltip(event, tooltipFormatter(d));
                }
            })
            .on('mouseout', function () {
                d3.select(this).attr('r', 5).attr('opacity', 0.7);
                hideTooltip();
            });
    }

    function renderLineChart(options) {
        const {
            container,
            data,
            xKey,
            yKey,
            seriesKey = null,
            height = 360,
            margin = { top: 20, right: 30, bottom: 50, left: 60 },
            yDomain = null,
            yReversed = false,
            tooltipFormatter,
        } = options;

        const el = clearContainer(container);
        if (!el) {
            return;
        }

        const width = el.clientWidth - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const xValues = [...new Set(data.map(d => d[xKey]))];
        const x = d3.scalePoint()
            .domain(xValues)
            .range([0, width])
            .padding(0.5);

        const yExtent = yDomain || d3.extent(data, d => d[yKey]);
        const yDomainFinal = yReversed ? [yExtent[1], yExtent[0]] : yExtent;
        const y = d3.scaleLinear()
            .domain(yDomainFinal)
            .nice()
            .range([innerHeight, 0]);

        const svg = d3.select(el)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', innerHeight + margin.top + margin.bottom)
            .append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        svg.append('g')
            .attr('class', 'grid')
            .call(d3.axisLeft(y).tickSize(-width).tickFormat(''));

        svg.append('g')
            .attr('transform', `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x))
            .attr('class', 'axis');

        svg.append('g')
            .call(d3.axisLeft(y))
            .attr('class', 'axis');

        const line = d3.line()
            .x(d => x(d[xKey]))
            .y(d => y(d[yKey]));

        const series = seriesKey
            ? d3.group(data, d => d[seriesKey])
            : new Map([['series', data]]);

        const color = d3.scaleOrdinal(d3.schemeCategory10)
            .domain([...series.keys()]);

        for (const [seriesName, seriesData] of series.entries()) {
            svg.append('path')
                .datum(seriesData)
                .attr('fill', 'none')
                .attr('stroke', color(seriesName))
                .attr('stroke-width', 2)
                .attr('d', line);

            svg.selectAll(`.point-${seriesName}`)
                .data(seriesData)
                .enter()
                .append('circle')
                .attr('cx', d => x(d[xKey]))
                .attr('cy', d => y(d[yKey]))
                .attr('r', 4)
                .attr('fill', color(seriesName))
                .on('mouseover', function (event, d) {
                    d3.select(this).attr('r', 6);
                    if (tooltipFormatter) {
                        showTooltip(event, tooltipFormatter(d));
                    }
                })
                .on('mouseout', function () {
                    d3.select(this).attr('r', 4);
                    hideTooltip();
                });
        }
    }

    // Team type utilities
    const INTERNATIONAL_TEAMS = new Set([
        'Argentina', 'Australia', 'England', 'Fiji', 'France', 'Georgia',
        'Ireland', 'Italy', 'Japan', 'Namibia', 'New Zealand', 'Romania',
        'Samoa', 'Scotland', 'South Africa', 'Tonga', 'Uruguay', 'USA',
        'Wales', 'Canada', 'Chile', 'Portugal', 'Spain'
    ]);

    const COMPETITION_TYPES = {
        'rugby-world': 'international',
        'six-nations': 'international',
        'rugby-championship': 'international',
        'autumn-nations': 'international',
        'internationals': 'international',
        'urc': 'club',
        'premiership': 'club',
        'top-14': 'club',
        'champions-cup': 'club',
        'challenge-cup': 'club'
    };

    function getTeamType(teamName, competition) {
        // Check competition first (most reliable)
        if (competition) {
            const compType = COMPETITION_TYPES[competition.toLowerCase()];
            if (compType) return compType;
        }
        // Fall back to team name matching
        return INTERNATIONAL_TEAMS.has(teamName) ? 'international' : 'club';
    }

    function filterDataByTeamType(data, teamType, teamKey = 'team', competitionKey = 'competition') {
        if (!teamType || teamType === 'all') return data;
        return data.filter(d => {
            const type = getTeamType(d[teamKey], d[competitionKey]);
            return type === teamType;
        });
    }

    // High-level embeddable widget functions
    function renderTeamComparisonWidget(options) {
        const {
            container,
            offenseData,
            defenseData,
            season,
            scoreType = 'tries',
            teamType = 'all',  // 'all', 'international', 'club'
            height = 500
        } = options;

        // Filter and merge data
        let filteredOffense = filterDataByTeamType(offenseData, teamType);
        let filteredDefense = filterDataByTeamType(defenseData, teamType);

        if (season) {
            filteredOffense = filteredOffense.filter(d => d.season === season);
            filteredDefense = filteredDefense.filter(d => d.season === season);
        }

        filteredOffense = filteredOffense.filter(d => d.score_type === scoreType);
        filteredDefense = filteredDefense.filter(d => d.score_type === scoreType);

        // Merge offense and defense by team
        const teamMap = new Map();
        filteredOffense.forEach(d => {
            teamMap.set(d.team, {
                team: d.team,
                season: d.season,
                offense: d.offense_mean || 0
            });
        });
        filteredDefense.forEach(d => {
            if (teamMap.has(d.team)) {
                teamMap.get(d.team).defense = d.defense_mean || 0;
            }
        });

        const comparisonData = Array.from(teamMap.values())
            .filter(d => d.offense !== undefined && d.defense !== undefined);

        renderScatterPlot({
            container,
            data: comparisonData,
            xKey: 'offense',
            yKey: 'defense',
            labelKey: 'team',
            height,
            xLabel: 'Offensive Strength',
            yLabel: 'Defensive Strength',
            tooltipFormatter: d => `<strong>${d.team}</strong><br/>Offense: ${d.offense.toFixed(2)}<br/>Defense: ${d.defense.toFixed(2)}`
        });
    }

    function renderPlayerComparisonWidget(options) {
        const {
            container,
            playerData,
            players = [],  // Array of player names to compare
            scoreType = 'tries',
            topN = 20,
            height = 600
        } = options;

        let filteredData = playerData.filter(d => d.score_type === scoreType);

        // If specific players requested, filter to those
        if (players.length > 0) {
            filteredData = filteredData.filter(d => players.includes(d.player));
        } else {
            // Otherwise show top N
            filteredData = filteredData
                .sort((a, b) => b.effect_mean - a.effect_mean)
                .slice(0, topN);
        }

        renderBarChartWithCI({
            container,
            data: filteredData,
            labelKey: 'player',
            meanKey: 'effect_mean',
            lowerKey: 'effect_lower',
            upperKey: 'effect_upper',
            color: scoreType === 'tries' ? '#198754' : '#0d6efd',
            height,
            tooltipFormatter: d => `<strong>${d.player}</strong><br/>Effect: ${d.effect_mean.toFixed(3)}<br/>95% CI: [${d.effect_lower.toFixed(3)}, ${d.effect_upper.toFixed(3)}]`
        });
    }

    function renderMatchPredictorWidget(options) {
        const {
            container,
            prediction,  // Prediction object with home/away data
            showDistribution = true
        } = options;

        const el = clearContainer(container);
        if (!el) return;

        // Create FiveThirtyEight-style narrative
        const favorite = prediction.home_win_prob > 0.5
            ? prediction.home_team
            : prediction.away_team;
        const winProb = Math.max(prediction.home_win_prob, prediction.away_win_prob);
        const margin = Math.abs(prediction.home_score_mean - prediction.away_score_mean);

        const confidence = winProb > 0.85 ? "heavily"
                         : winProb > 0.70 ? "strongly"
                         : "slightly";

        // Build widget HTML
        const html = `
            <div class="match-predictor-widget">
                <div class="prediction-narrative" style="padding: 20px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px;">
                    <p style="font-size: 18px; line-height: 1.6; margin: 0;">
                        <strong style="color: #0d6efd;">${favorite}</strong> is ${confidence} favored to win by
                        <strong>${margin.toFixed(1)} points</strong> with
                        <strong>${(winProb * 100).toFixed(0)}%</strong> confidence.
                    </p>
                    <p style="font-size: 14px; color: #6c757d; margin: 10px 0 0 0;">
                        Expected score: ${prediction.home_team} ${prediction.home_score_mean.toFixed(0)} -
                        ${prediction.away_team} ${prediction.away_score_mean.toFixed(0)}
                    </p>
                </div>

                <div class="win-probability" style="margin-bottom: 20px;">
                    <h5 style="margin-bottom: 10px;">Win Probability</h5>
                    <div style="display: flex; height: 40px; border-radius: 4px; overflow: hidden;">
                        <div style="width: ${(prediction.home_win_prob * 100).toFixed(1)}%; background: #0d6efd; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                            ${(prediction.home_win_prob * 100).toFixed(0)}%
                        </div>
                        ${prediction.draw_prob > 0.01 ? `
                        <div style="width: ${(prediction.draw_prob * 100).toFixed(1)}%; background: #6c757d; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px;">
                            Draw ${(prediction.draw_prob * 100).toFixed(0)}%
                        </div>` : ''}
                        <div style="width: ${(prediction.away_win_prob * 100).toFixed(1)}%; background: #dc3545; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                            ${(prediction.away_win_prob * 100).toFixed(0)}%
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 14px; color: #6c757d;">
                        <span>${prediction.home_team}</span>
                        <span>${prediction.away_team}</span>
                    </div>
                </div>

                <div class="score-ranges" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div style="padding: 15px; background: rgba(13, 110, 253, 0.1); border-radius: 8px;">
                        <strong style="display: block; margin-bottom: 5px;">${prediction.home_team}</strong>
                        <div style="font-size: 24px; font-weight: bold; color: #0d6efd;">${prediction.home_score_mean.toFixed(1)}</div>
                        <div style="font-size: 12px; color: #6c757d;">Range: ${prediction.home_score_lower} - ${prediction.home_score_upper}</div>
                    </div>
                    <div style="padding: 15px; background: rgba(220, 53, 69, 0.1); border-radius: 8px;">
                        <strong style="display: block; margin-bottom: 5px;">${prediction.away_team}</strong>
                        <div style="font-size: 24px; font-weight: bold; color: #dc3545;">${prediction.away_score_mean.toFixed(1)}</div>
                        <div style="font-size: 12px; color: #6c757d;">Range: ${prediction.away_score_lower} - ${prediction.away_score_upper}</div>
                    </div>
                </div>
            </div>
        `;

        el.innerHTML = html;
    }

    global.RugbyCharts = {
        renderBarChartWithCI,
        renderScatterPlot,
        renderLineChart,
        // High-level embeddable widgets
        renderTeamComparisonWidget,
        renderPlayerComparisonWidget,
        renderMatchPredictorWidget,
        // Utility functions
        getTeamType,
        filterDataByTeamType,
        renderMultiLineChart: function(options) {
            // Wrapper that uses renderLineChart with seriesKey
            const {
                container,
                data,
                xKey,
                yKey,
                seriesKey,
                yLabel = '',
                xLabel = '',
                yReversed = false,
                height = 400,
                margin = { top: 20, right: 100, bottom: 50, left: 60 },
                tooltipFormatter,
            } = options;

            const el = clearContainer(container);
            if (!el) {
                return;
            }

            const width = el.clientWidth - margin.left - margin.right;
            const innerHeight = height - margin.top - margin.bottom;

            const xValues = [...new Set(data.map(d => d[xKey]))];
            const x = d3.scalePoint()
                .domain(xValues)
                .range([0, width])
                .padding(0.5);

            const yExtent = d3.extent(data, d => d[yKey]);
            const yDomainFinal = yReversed ? [yExtent[1], yExtent[0]] : yExtent;
            const y = d3.scaleLinear()
                .domain(yDomainFinal)
                .nice()
                .range([innerHeight, 0]);

            const svg = d3.select(el)
                .append('svg')
                .attr('width', width + margin.left + margin.right)
                .attr('height', innerHeight + margin.top + margin.bottom)
                .append('g')
                .attr('transform', `translate(${margin.left},${margin.top})`);

            // Add grid
            svg.append('g')
                .attr('class', 'grid')
                .call(d3.axisLeft(y).tickSize(-width).tickFormat(''));

            // Add axes
            svg.append('g')
                .attr('transform', `translate(0,${innerHeight})`)
                .call(d3.axisBottom(x))
                .attr('class', 'axis');

            svg.append('g')
                .call(d3.axisLeft(y))
                .attr('class', 'axis');

            // Add axis labels
            if (xLabel) {
                svg.append('text')
                    .attr('x', width / 2)
                    .attr('y', innerHeight + 35)
                    .attr('text-anchor', 'middle')
                    .attr('class', 'axis-label')
                    .text(xLabel);
            }

            if (yLabel) {
                svg.append('text')
                    .attr('transform', 'rotate(-90)')
                    .attr('y', 0 - margin.left + 15)
                    .attr('x', 0 - (innerHeight / 2))
                    .attr('text-anchor', 'middle')
                    .attr('class', 'axis-label')
                    .text(yLabel);
            }

            const line = d3.line()
                .x(d => x(d[xKey]))
                .y(d => y(d[yKey]));

            const series = d3.group(data, d => d[seriesKey]);
            const color = d3.scaleOrdinal(d3.schemeCategory10)
                .domain([...series.keys()]);

            // Add legend
            const legend = svg.append('g')
                .attr('class', 'legend')
                .attr('transform', `translate(${width + 15}, 0)`);

            let legendY = 0;
            for (const [seriesName, seriesData] of series.entries()) {
                svg.append('path')
                    .datum(seriesData)
                    .attr('fill', 'none')
                    .attr('stroke', color(seriesName))
                    .attr('stroke-width', 2.5)
                    .attr('d', line);

                svg.selectAll(`.point-${seriesName}`)
                    .data(seriesData)
                    .enter()
                    .append('circle')
                    .attr('cx', d => x(d[xKey]))
                    .attr('cy', d => y(d[yKey]))
                    .attr('r', 4)
                    .attr('fill', color(seriesName))
                    .on('mouseover', function (event, d) {
                        d3.select(this).attr('r', 6);
                        if (tooltipFormatter) {
                            showTooltip(event, tooltipFormatter(d));
                        }
                    })
                    .on('mouseout', function () {
                        d3.select(this).attr('r', 4);
                        hideTooltip();
                    });

                // Add legend entry
                legend.append('rect')
                    .attr('x', 0)
                    .attr('y', legendY)
                    .attr('width', 12)
                    .attr('height', 12)
                    .attr('fill', color(seriesName));

                legend.append('text')
                    .attr('x', 18)
                    .attr('y', legendY + 10)
                    .attr('font-size', '12px')
                    .text(seriesName);

                legendY += 20;
            }
        },
        utils: {
            clearContainer,
            showTooltip,
            hideTooltip,
        }
    };
})(window);
