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

    global.RugbyCharts = {
        renderBarChartWithCI,
        renderScatterPlot,
        renderLineChart,
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
