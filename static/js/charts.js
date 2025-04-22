function createChart(chartData) {
    const ctx = document.getElementById('diffChart').getContext('2d');
    const diffChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.timestamps,
            datasets: [
                {
                    label: 'URLs Added',
                    data: chartData.added,
                    backgroundColor: 'rgba(75, 192, 75, 0.2)',
                    borderColor: 'rgba(75, 192, 75, 1)',
                    borderWidth: 2,
                    pointRadius: 4
                },
                {
                    label: 'URLs Deleted',
                    data: chartData.deleted,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of URLs'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Scan Time'
                    }
                }
            }
        }
    });
}
