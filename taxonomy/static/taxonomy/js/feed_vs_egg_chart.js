function renderFeedVsEggChart(feedVsEggData) {
    // SVG領域の設定
    const margin = {top: 20, right: 60, bottom: 40, left: 50};
    const width = 800 - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select("#chart-area").append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left}, ${margin.top})`);

    // X軸: 日付
    const x = d3.scaleTime()
        .domain(d3.extent(feedVsEggData, d => new Date(d.recorded_date)))
        .range([0, width]);
    svg.append("g")
        .attr("transform", `translate(0, ${height})`)
        .call(d3.axisBottom(x));

    // Y軸: 餌投入量
    const yLeft = d3.scaleLinear()
        .domain([0, d3.max(feedVsEggData, d => d.total_feed)])
        .range([height, 0]);
    svg.append("g")
        .call(d3.axisLeft(yLeft))
        .style("fill", "steelblue");

    // Y軸右: 卵の生産数
    const yRight = d3.scaleLinear()
        .domain([0, d3.max(feedVsEggData, d => d.total_eggs)])
        .range([height, 0]);
    svg.append("g")
        .attr("transform", `translate(${width}, 0)`)
        .call(d3.axisRight(yRight))
        .style("fill", "orange");

    // 餌投入量: 折れ線
    svg.append("path")
        .datum(feedVsEggData)
        .attr("fill", "none")
        .attr("stroke", "steelblue")
        .attr("stroke-width", 2)
        .attr("d", d3.line()
            .x(d => x(new Date(d.recorded_date)))
            .y(d => yLeft(d.total_feed))
        );

    // 卵生産数: オレンジの点プロット
    svg.selectAll(".dot")
        .data(feedVsEggData)
        .enter()
        .append("circle")
        .attr("cx", d => x(new Date(d.recorded_date)))
        .attr("cy", d => yRight(d.total_eggs))
        .attr("r", 4)
        .style("fill", "orange")
        .style("opacity", 0.8);

    // ラベル追加
    svg.append("text")
        .attr("x", width / 2)
        .attr("y", height + margin.bottom)
        .attr("text-anchor", "middle")
        .text("日付");

    svg.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -height / 2)
        .attr("y", -margin.left + 10)
        .attr("text-anchor", "middle")
        .style("fill", "steelblue")
        .text("餌投入量 (g)");

    svg.append("text")
        .attr("transform", `translate(${width + 50}, ${height / 2}) rotate(90)`)
        .attr("text-anchor", "middle")
        .style("fill", "orange")
        .text("卵 生産数 (個)");
}
