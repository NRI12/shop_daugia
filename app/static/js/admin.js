document.addEventListener('DOMContentLoaded', function() {
    // Use the data passed from Flask directly
    updateDashboardStats(basic_stats);
    initializeSalesChart(sales_data);
    updateLatestOrders(latest_orders);
    updateMetricsCards(user_metrics);
});


function updateDashboardStats(stats) {
    document.getElementById('total-users').textContent = stats.total_users;
    document.getElementById('total-auctions').textContent = stats.total_auctions;
    document.getElementById('total-revenue').textContent = 
        new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' })
        .format(stats.total_revenue);
    document.getElementById('active-auctions').textContent = stats.active_auctions;
}

function initializeSalesChart(salesData) {
    const options = {
        chart: {
            type: 'area',
            height: 350,
            toolbar: {
                show: false
            }
        },
        series: [{
            name: 'Sales',
            data: salesData.map(item => item.amount)
        }],
        xaxis: {
            categories: salesData.map(item => item.month),
            labels: {
                rotate: -45
            }
        },
        yaxis: {
            labels: {
                formatter: function(value) {
                    return new Intl.NumberFormat('vi-VN', 
                        { style: 'currency', currency: 'VND' })
                        .format(value);
                }
            }
        },
        colors: ['#00ab55'],
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.7,
                opacityTo: 0.3
            }
        },
        stroke: {
            curve: 'smooth'
        },
        dataLabels: {
            enabled: false
        }
    };

    const chart = new ApexCharts(
        document.querySelector("#sales-chart"), 
        options
    );
    chart.render();
}

function updateLatestOrders(orders) {
    const tableBody = document.querySelector('.table tbody');
    tableBody.innerHTML = orders.map(order => `
        <tr>
            <td>${order.id}</td>
            <td>${order.product}</td>
            <td>${order.buyer}</td>
            <td>${new Intl.NumberFormat('vi-VN', 
                { style: 'currency', currency: 'VND' })
                .format(order.amount)}</td>
            <td>${order.date}</td>
        </tr>
    `).join('');
}

function updateMetricsCards(metrics) {
    document.getElementById('active-users').textContent = metrics.active_24h;
    document.getElementById('new-users').textContent = metrics.new_7d;
}