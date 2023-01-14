function BarChart_stack(chart_id, data){
    const ctx = document.getElementById(chart_id).getContext("2d");
    new Chart(ctx, {
        type: 'bar',
        data: data,
        options: {
            responsive: false,
            legend: {
                display: true
            },
            scales: {
                xAxes: [{
                    stacked: true,
                    gridLines: {
                        display: false
                    }
                }],
                yAxes: [{
                    stacked: true,
                    gridLines: {
                        borderDash: [5, 5]
                    },
                    ticks: {
                        max: 40000
                    }
                }],
            }
        }
    });
}
