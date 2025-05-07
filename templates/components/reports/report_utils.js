/**
 * Utility functions for sales reports
 */

// Chart color schemes
const chartColors = {
    primary: '#F9A826',
    primaryLight: 'rgba(249, 168, 38, 0.2)',
    secondary: '#3B82F6',
    secondaryLight: 'rgba(59, 130, 246, 0.2)',
    success: '#10B981',
    successLight: 'rgba(16, 185, 129, 0.2)',
    danger: '#EF4444',
    dangerLight: 'rgba(239, 68, 68, 0.2)',
    purple: '#8B5CF6',
    purpleLight: 'rgba(139, 92, 246, 0.2)',
    gray: '#6B7280',
    grayLight: 'rgba(107, 114, 128, 0.2)'
};

// Common chart options
const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: '#E5E7EB'
            }
        },
        tooltip: {
            backgroundColor: '#1F2937',
            titleColor: '#F9A826',
            bodyColor: '#E5E7EB',
            borderColor: '#374151',
            borderWidth: 1,
            padding: 10,
            boxPadding: 5,
            usePointStyle: true,
            callbacks: {
                labelPointStyle: function(context) {
                    return {
                        pointStyle: 'rectRounded',
                        rotation: 0
                    };
                }
            }
        }
    },
    scales: {
        x: {
            grid: {
                color: 'rgba(75, 85, 99, 0.2)'
            },
            ticks: {
                color: '#9CA3AF'
            }
        },
        y: {
            grid: {
                color: 'rgba(75, 85, 99, 0.2)'
            },
            ticks: {
                color: '#9CA3AF'
            }
        }
    }
};

// Create a time series chart
function createTimeSeriesChart(ctx, labels, data, options = {}) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: options.label || 'Revenue',
                data: data,
                borderColor: options.borderColor || chartColors.primary,
                backgroundColor: options.backgroundColor || chartColors.primaryLight,
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            ...commonChartOptions,
            ...options
        }
    });
}

// Create a bar chart
function createBarChart(ctx, labels, data, options = {}) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: options.label || 'Data',
                data: data,
                backgroundColor: options.backgroundColor || chartColors.primary,
                borderColor: options.borderColor || chartColors.primary,
                borderWidth: 1
            }]
        },
        options: {
            ...commonChartOptions,
            ...options
        }
    });
}

// Create a pie chart
function createPieChart(ctx, labels, data, options = {}) {
    // Generate colors if not provided
    const backgroundColors = options.backgroundColors || 
        labels.map((_, i) => {
            const colors = [
                chartColors.primary,
                chartColors.secondary,
                chartColors.success,
                chartColors.danger,
                chartColors.purple,
                '#14B8A6', // teal
                '#F59E0B', // amber
                '#EC4899', // pink
                '#6366F1', // indigo
                '#84CC16'  // lime
            ];
            return colors[i % colors.length];
        });

    return new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderColor: '#1F2937',
                borderWidth: 1
            }]
        },
        options: {
            ...commonChartOptions,
            plugins: {
                ...commonChartOptions.plugins,
                legend: {
                    position: 'right',
                    labels: {
                        color: '#E5E7EB',
                        padding: 15,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                }
            }
        }
    });
}

// Export table to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const rows = table.querySelectorAll('tr');
    let csvContent = "data:text/csv;charset=utf-8,";
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowData = Array.from(cells)
            .map(cell => {
                // Remove any HTML and get just the text
                let text = cell.textContent.trim();
                // Escape quotes and wrap in quotes if contains comma
                if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                    text = '"' + text.replace(/"/g, '""') + '"';
                }
                return text;
            })
            .join(',');
        csvContent += rowData + '\r\n';
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Download chart as image
function downloadChartAsImage(chartId, filename) {
    const canvas = document.getElementById(chartId);
    if (!canvas) return;
    
    const link = document.createElement('a');
    link.download = filename;
    link.href = canvas.toDataURL('image/png');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Initialize export buttons
function initExportButtons() {
    document.querySelectorAll('.export-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tableId = this.getAttribute('data-table');
            const filename = `sales_report_${new Date().toISOString().slice(0, 10)}.csv`;
            exportTableToCSV(tableId, filename);
        });
    });
    
    document.querySelectorAll('.download-chart').forEach(button => {
        button.addEventListener('click', function() {
            const chartId = this.getAttribute('data-chart');
            const filename = `chart_${chartId}_${new Date().toISOString().slice(0, 10)}.png`;
            downloadChartAsImage(chartId, filename);
        });
    });
}

// Initialize print functionality
function initPrintButton() {
    document.getElementById('print-report')?.addEventListener('click', function() {
        window.print();
    });
}

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    initExportButtons();
    initPrintButton();
});
