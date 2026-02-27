// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '\u2600' : '\u263D';
    }
}

// Set icon on load
document.addEventListener('DOMContentLoaded', function() {
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(theme);
});

// Pause HTMX polling when tab is hidden
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        document.body.setAttribute('hx-disable', '');
    } else {
        document.body.removeAttribute('hx-disable');
    }
});

// Chart.js response time chart
var responseChart = null;

function initResponseChart(data) {
    const canvas = document.getElementById('response-chart');
    if (!canvas || !data || data.length === 0) return;

    // Destroy existing chart if any
    if (responseChart) {
        responseChart.destroy();
        responseChart = null;
    }

    const ctx = canvas.getContext('2d');
    responseChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.time),
            datasets: [{
                label: 'Response Time (ms)',
                data: data.map(d => d.response_time_ms),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: data.length > 100 ? 0 : 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    display: true,
                    ticks: { maxTicksLimit: 12 }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'ms' }
                }
            }
        }
    });
}

// Reinitialize chart after HTMX swap
document.addEventListener('htmx:afterSettle', function() {
    const canvas = document.getElementById('response-chart');
    if (canvas && window.chartData) {
        initResponseChart(window.chartData);
    }
});
