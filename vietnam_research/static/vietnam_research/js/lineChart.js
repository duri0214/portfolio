/**
 * ChartJsを使って線グラフを作成する
 * @param {string} chart_id
 * @param {*} data
 * @see https://www.chartjs.org/docs/latest/getting-started/
 */
const LineChart = function (chart_id, data) {

    const ctx = document.getElementById(chart_id).getContext('2d');

    new Chart(ctx, {
        // The type of chart we want to create
        type: 'line',

        // The data for our dataset
        data: data,

        // Configuration options go here
        options: {
            responsive: false,
            maintainAspectRatio: false
        }
    });
}
