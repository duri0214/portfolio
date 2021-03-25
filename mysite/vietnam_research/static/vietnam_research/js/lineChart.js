const LineChart = function (chart_id, data) {

  var ctx = document.getElementById(chart_id).getContext('2d');

  var chart = new Chart(ctx, {
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