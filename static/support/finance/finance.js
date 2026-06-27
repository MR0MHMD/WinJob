// static/support/finance/finance.js

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // ================================================================ //
    // 1. گرفتن دیتا از window.FINANCE_CHART_DATA
    // ================================================================ //
    const chartData = window.FINANCE_CHART_DATA;

    if (!chartData) {
        console.warn('دیتای چارت مالی موجود نیست.');
        return;
    }

    // ================================================================ //
    // 2. رنگ‌های تم دارک
    // ================================================================ //
    const colors = {
        primary: '#fd5631',
        success: '#07c98b',
        danger: '#f23c49',
        info: '#3c76f2',
        warning: '#fdbc31',
        purple: '#8b5cf6',
        gold: '#f59e0b',
        text: '#9691a4',
        border: 'rgba(255,255,255,0.06)',
        grid: 'rgba(255,255,255,0.04)',
    };

    // تنظیمات پیش‌فرض Chart.js
    Chart.defaults.color = colors.text;
    Chart.defaults.borderColor = colors.border;
    Chart.defaults.font.family = 'IRANSans, sans-serif';

    // ================================================================ //
    // 3. نمودار روزانه (درآمد و سود)
    // ================================================================ //
    const dailyCanvas = document.getElementById('dailyChart');
    if (dailyCanvas) {
        const dailyCtx = dailyCanvas.getContext('2d');
        new Chart(dailyCtx, {
            type: 'bar',
            data: {
                labels: chartData.dailyLabels || [],
                datasets: [
                    {
                        label: 'درآمد ناخالص',
                        data: chartData.dailyIncome || [],
                        backgroundColor: 'rgba(7,201,139,0.2)',
                        borderColor: colors.success,
                        borderWidth: 2,
                        borderRadius: 4,
                        order: 1,
                    },
                    {
                        label: 'سود خالص (کمیسیون)',
                        data: chartData.dailyCommission || [],
                        backgroundColor: 'rgba(245,158,11,0.25)',
                        borderColor: colors.gold,
                        borderWidth: 2,
                        borderRadius: 4,
                        order: 0,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        backgroundColor: 'rgba(31,27,45,0.9)',
                        borderColor: colors.border,
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ': ' + context.parsed.y.toLocaleString() + ' تومان';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: colors.grid,
                            drawBorder: false,
                        },
                        ticks: {
                            callback: function (value) {
                                if (value >= 1000000) {
                                    return (value / 1000000).toFixed(1) + 'M';
                                } else if (value >= 1000) {
                                    return (value / 1000).toFixed(1) + 'K';
                                }
                                return value;
                            }
                        }
                    },
                    x: {
                        grid: {display: false}
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
            }
        });
    }

    // ================================================================ //
    // 4. نمودار دایره‌ای سهم‌بندی
    // ================================================================ //
    const pieCanvas = document.getElementById('revenuePieChart');
    if (pieCanvas) {
        const pieCtx = pieCanvas.getContext('2d');
        const pieColors = [colors.info, colors.purple, colors.gold];

        new Chart(pieCtx, {
            type: 'doughnut',
            data: {
                labels: chartData.revenueLabels || [],
                datasets: [{
                    data: chartData.revenueData || [],
                    backgroundColor: pieColors,
                    borderColor: 'rgba(31,27,45,0.8)',
                    borderWidth: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        backgroundColor: 'rgba(31,27,45,0.9)',
                        borderColor: colors.border,
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        callbacks: {
                            label: function (context) {
                                let total = context.dataset.data.reduce((a, b) => a + b, 0);
                                let percentage = total > 0 ? (context.parsed / total * 100).toFixed(1) : 0;
                                return context.label + ': ' + context.parsed.toLocaleString() + ' تومان (' + percentage + '%)';
                            }
                        }
                    }
                },
                cutout: '65%',
            }
        });
    }

});