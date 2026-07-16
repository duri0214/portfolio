function solveQuadraticCoefficients(points) {
    const sums = points.reduce((acc, point) => {
        const x2 = point.x * point.x;
        acc.x += point.x;
        acc.x2 += x2;
        acc.x3 += x2 * point.x;
        acc.x4 += x2 * x2;
        acc.y += point.y;
        acc.xy += point.x * point.y;
        acc.x2y += x2 * point.y;
        return acc;
    }, {x: 0, x2: 0, x3: 0, x4: 0, y: 0, xy: 0, x2y: 0});

    const matrix = [
        [sums.x4, sums.x3, sums.x2, sums.x2y],
        [sums.x3, sums.x2, sums.x, sums.xy],
        [sums.x2, sums.x, points.length, sums.y],
    ];

    for (let column = 0; column < 3; column += 1) {
        let pivotRow = column;
        for (let row = column + 1; row < 3; row += 1) {
            if (Math.abs(matrix[row][column]) > Math.abs(matrix[pivotRow][column])) {
                pivotRow = row;
            }
        }
        if (Math.abs(matrix[pivotRow][column]) < 1e-9) {
            return null;
        }
        [matrix[column], matrix[pivotRow]] = [matrix[pivotRow], matrix[column]];

        const pivot = matrix[column][column];
        for (let cell = column; cell < 4; cell += 1) {
            matrix[column][cell] /= pivot;
        }
        for (let row = 0; row < 3; row += 1) {
            if (row === column) {
                continue;
            }
            const factor = matrix[row][column];
            for (let cell = column; cell < 4; cell += 1) {
                matrix[row][cell] -= factor * matrix[column][cell];
            }
        }
    }

    return {
        a: matrix[0][3],
        b: matrix[1][3],
        c: matrix[2][3],
    };
}

function buildQuadraticTrendPoints(parsedData) {
    if (parsedData.length < 3) {
        return [];
    }

    const dayMs = 24 * 60 * 60 * 1000;
    const firstTime = parsedData[0].date.getTime();
    const points = parsedData.map((item) => ({
        x: (item.date.getTime() - firstTime) / dayMs,
        y: item.laying_rate,
    }));
    const minX = d3.min(points, (point) => point.x);
    const maxX = d3.max(points, (point) => point.x);
    if (minX === maxX) {
        return [];
    }

    const coefficients = solveQuadraticCoefficients(points);
    if (!coefficients) {
        return [];
    }

    const stepCount = 80;
    return d3.range(stepCount + 1).map((index) => {
        const xValue = minX + ((maxX - minX) * index) / stepCount;
        return {
            date: new Date(firstTime + xValue * dayMs),
            laying_rate: coefficients.a * xValue * xValue + coefficients.b * xValue + coefficients.c,
        };
    });
}

function renderFeedVsEggChart(feedVsEggData) {
    const chartArea = document.querySelector("#feed-vs-egg-chart");
    chartArea.innerHTML = "";

    if (!feedVsEggData.length) {
        chartArea.innerHTML = '<div class="observation-chart-empty">観察データがありません。</div>';
        return;
    }

    const parsedData = feedVsEggData.map((item) => ({
        ...item,
        date: new Date(item.recorded_date),
    }));
    const bounds = chartArea.getBoundingClientRect();
    const margin = {top: 36, right: 56, bottom: 82, left: 52};
    const outerWidth = Math.max(bounds.width || 720, 720);
    const outerHeight = 420;
    const width = outerWidth - margin.left - margin.right;
    const height = outerHeight - margin.top - margin.bottom;

    const svg = d3.select(chartArea)
        .append("svg")
        .attr("viewBox", `0 0 ${outerWidth} ${outerHeight}`)
        .attr("role", "img")
        .attr("aria-label", "給餌量、産卵率、二次近似、天気の推移");

    const plot = svg.append("g")
        .attr("transform", `translate(${margin.left}, ${margin.top})`);

    const x = d3.scaleTime()
        .domain(d3.extent(parsedData, (d) => d.date))
        .range([0, width]);
    const trendPoints = buildQuadraticTrendPoints(parsedData);
    const rateMax = Math.max(
        d3.max(parsedData, (d) => d.laying_rate) || 1,
        d3.max(trendPoints, (d) => d.laying_rate) || 0,
    );
    const yRate = d3.scaleLinear()
        .domain([0, Math.ceil(rateMax + 10)])
        .nice()
        .range([height, 0]);
    const feedWeights = Array.from(new Set(parsedData.map((d) => d.total_feed))).sort((a, b) => b - a);
    const feedColor = d3.scaleOrdinal()
        .domain(feedWeights)
        .range(["#1d4ed8", "#15803d", "#7c2d12", "#6d28d9"]);
    const markerWidth = Math.max(width / parsedData.length * 0.55, 3);
    const feedMarkerHeight = 12;

    plot.append("g")
        .attr("class", "grid")
        .call(d3.axisLeft(yRate).ticks(5).tickSize(-width).tickFormat(""))
        .call((g) => g.selectAll("line").attr("stroke", "#e5e7eb"))
        .call((g) => g.select(".domain").remove());

    plot.selectAll(".feed-marker")
        .data(parsedData)
        .enter()
        .append("rect")
        .attr("class", "feed-marker")
        .attr("x", (d) => x(d.date) - markerWidth / 2)
        .attr("y", height + 14)
        .attr("width", markerWidth)
        .attr("height", feedMarkerHeight)
        .attr("fill", (d) => feedColor(d.total_feed))
        .attr("rx", 1);

    const rateLine = d3.line()
        .x((d) => x(d.date))
        .y((d) => yRate(d.laying_rate));

    plot.append("path")
        .datum(parsedData)
        .attr("fill", "none")
        .attr("stroke", "#0f766e")
        .attr("stroke-width", 2.5)
        .attr("d", rateLine);

    if (trendPoints.length) {
        plot.append("path")
            .datum(trendPoints)
            .attr("class", "quadratic-trend-line")
            .attr("fill", "none")
            .attr("stroke", "#334155")
            .attr("stroke-width", 2)
            .attr("stroke-dasharray", "5 5")
            .attr("opacity", 0.85)
            .attr("d", rateLine);
    }

    const tooltip = d3.select("body")
        .append("div")
        .attr("class", "observation-chart-tooltip")
        .style("display", "none");

    plot.selectAll(".rate-point")
        .data(parsedData)
        .enter()
        .append("circle")
        .attr("class", "rate-point")
        .attr("cx", (d) => x(d.date))
        .attr("cy", (d) => yRate(d.laying_rate))
        .attr("r", 4)
        .attr("fill", "#0f766e")
        .on("mouseenter", (event, d) => {
            tooltip
                .style("display", "block")
                .html([
                    d.recorded_date,
                    `給餌量: ${d.total_feed}g`,
                    `産卵数: ${d.total_eggs}個`,
                    `産卵率: ${d.laying_rate}%`,
                    `天気: ${d.weather_name}`,
                ].join("<br>"));
        })
        .on("mousemove", (event) => {
            tooltip
                .style("left", `${event.clientX + 12}px`)
                .style("top", `${event.clientY + 12}px`);
        })
        .on("mouseleave", () => tooltip.style("display", "none"));

    plot.selectAll(".weather-dot")
        .data(parsedData)
        .enter()
        .append("text")
        .attr("x", (d) => x(d.date))
        .attr("y", height + 38)
        .attr("text-anchor", "middle")
        .attr("font-size", 10)
        .attr("fill", "#64748b")
        .text((d) => d.weather_name.slice(0, 1));

    plot.append("g")
        .attr("transform", `translate(0, ${height})`)
        .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%m/%d")))
        .call((g) => g.selectAll("text").attr("fill", "#475467"));

    plot.append("g")
        .call(d3.axisLeft(yRate).ticks(5).tickFormat((d) => `${d}%`))
        .call((g) => g.selectAll("text").attr("fill", "#0f766e"));

    svg.append("text")
        .attr("x", margin.left)
        .attr("y", 18)
        .attr("fill", "#475467")
        .attr("font-size", 12)
        .text("線: 産卵率 / 点線: 二次近似 / 下段色: 給餌量 / 下段文字: 天気");

    const legend = svg.append("g")
        .attr("transform", `translate(${margin.left}, ${outerHeight - 18})`);
    feedWeights.forEach((weight, index) => {
        const item = legend.append("g")
            .attr("transform", `translate(${index * 110}, 0)`);
        item.append("rect")
            .attr("width", 14)
            .attr("height", 14)
            .attr("fill", feedColor(weight));
        item.append("text")
            .attr("x", 20)
            .attr("y", 11)
            .attr("fill", "#475467")
            .attr("font-size", 12)
            .text(`${weight}g`);
    });
}

function initializeFeedVsEggChart() {
    const chartArea = document.querySelector("#feed-vs-egg-chart");
    if (!chartArea) {
        return;
    }

    try {
        const rawData = chartArea.getAttribute("data-feed-data");
        const feedVsEggData = rawData ? JSON.parse(rawData) : [];
        renderFeedVsEggChart(feedVsEggData);
    } catch (error) {
        console.error("Error parsing or rendering feed vs. egg chart:", error);
    }
}

document.addEventListener("DOMContentLoaded", initializeFeedVsEggChart);
window.addEventListener("resize", () => {
    window.clearTimeout(window.feedVsEggResizeTimer);
    window.feedVsEggResizeTimer = window.setTimeout(initializeFeedVsEggChart, 150);
});
