// static/support/finance/finance.js

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    const chartData = window.FINANCE_CHART_DATA;

    if (!chartData) {
        console.warn('دیتای چارت مالی موجود نیست.');
        return;
    }

    // ================================================================ //
    // رنگ‌ها
    // ================================================================ //
    const colors = {
        primary: '#fd5631',
        success: '#07c98b',
        danger: '#f23c49',
        info: '#3c76f2',
        warning: '#fdbc31',
        purple: '#8b5cf6',
        cyan: '#06b6d4',
        pink: '#ec4899',
        gold: '#f59e0b',
        site: '#9ca3af',
        text: '#9691a4',
        border: 'rgba(255,255,255,0.06)',
        grid: 'rgba(255,255,255,0.04)',
    };

    Chart.defaults.color = colors.text;
    Chart.defaults.borderColor = colors.border;
    Chart.defaults.font.family = 'IRANSans, sans-serif';
    Chart.defaults.font.size = 11;

    const tooltipConfig = {
        backgroundColor: 'rgba(31,27,45,0.95)',
        borderColor: colors.border,
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        titleColor: '#fff',
        bodyColor: '#fff',
        titleFont: { size: 12 },
        bodyFont: { size: 12 },
    };

    const formatNumber = (value) => Number(value).toLocaleString('fa-IR');

    const formatShortNumber = (value) => {
        if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
        if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
        return value;
    };

    // ================================================================ //
    // 1. نمودار مقایسه ۳ ماه
    // ================================================================ //
    const compareMonthsCanvas = document.getElementById('compareMonthsChart');
    if (compareMonthsCanvas) {
        const ctx = compareMonthsCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.compareMonthsLabels || [],
                datasets: [
                    {
                        label: 'درآمد کل',
                        data: chartData.compareMonthsIncome || [],
                        backgroundColor: 'rgba(7,201,139,0.25)',
                        borderColor: colors.success,
                        borderWidth: 2,
                        borderRadius: 8,
                        barPercentage: 0.65,
                    },
                    {
                        label: 'سود خالص',
                        data: chartData.compareMonthsCommission || [],
                        backgroundColor: 'rgba(245,158,11,0.3)',
                        borderColor: colors.gold,
                        borderWidth: 2,
                        borderRadius: 8,
                        barPercentage: 0.65,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...tooltipConfig,
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ': ' + formatNumber(context.parsed.y) + ' تومان';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: colors.grid, drawBorder: false },
                        ticks: { callback: formatShortNumber }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 12, weight: '600' } }
                    }
                },
                interaction: { intersect: false, mode: 'index' },
            }
        });
    }

    // ================================================================ //
    // 2. نمودار روزانه ماه جاری
    // ================================================================ //
    const currentMonthDailyCanvas = document.getElementById('currentMonthDailyChart');
    if (currentMonthDailyCanvas) {
        const ctx = currentMonthDailyCanvas.getContext('2d');

        const gradientIncome = ctx.createLinearGradient(0, 0, 0, 300);
        gradientIncome.addColorStop(0, 'rgba(7,201,139,0.4)');
        gradientIncome.addColorStop(1, 'rgba(7,201,139,0.02)');

        const gradientCommission = ctx.createLinearGradient(0, 0, 0, 300);
        gradientCommission.addColorStop(0, 'rgba(245,158,11,0.4)');
        gradientCommission.addColorStop(1, 'rgba(245,158,11,0.02)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.currentMonthDailyLabels || [],
                datasets: [
                    {
                        label: 'درآمد کل',
                        data: chartData.currentMonthDailyIncome || [],
                        borderColor: colors.success,
                        backgroundColor: gradientIncome,
                        borderWidth: 2.5,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: colors.success,
                        pointBorderColor: '#1f1b2d',
                        pointBorderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    },
                    {
                        label: 'سود خالص',
                        data: chartData.currentMonthDailyCommission || [],
                        borderColor: colors.gold,
                        backgroundColor: gradientCommission,
                        borderWidth: 2.5,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: colors.gold,
                        pointBorderColor: '#1f1b2d',
                        pointBorderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...tooltipConfig,
                        callbacks: {
                            title: function (context) {
                                return 'روز ' + context[0].label;
                            },
                            label: function (context) {
                                return context.dataset.label + ': ' + formatNumber(context.parsed.y) + ' تومان';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: colors.grid, drawBorder: false },
                        ticks: { callback: formatShortNumber }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    }
                },
                interaction: { intersect: false, mode: 'index' },
            }
        });
    }

    // ================================================================ //
    // 3. Pie سهم‌بندی درآمد (۵ بخش)
    // ================================================================ //
    const revenuePieCanvas = document.getElementById('revenuePieChart');
    if (revenuePieCanvas) {
        const ctx = revenuePieCanvas.getContext('2d');

        // ۵ رنگ: ناشران، محتوا، کمیسیون، مالیات، کیف پول
        const pieColors = [
            colors.info,     // ناشران - آبی
            colors.purple,   // محتوا - بنفش
            colors.gold,     // کمیسیون - طلایی
            colors.warning,  // مالیات - زرد
        ];

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.revenueLabels || [],
                datasets: [{
                    data: chartData.revenueData || [],
                    backgroundColor: pieColors,
                    borderColor: '#1f1b2d',
                    borderWidth: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: colors.text,
                            font: { size: 10 },
                            padding: 8,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            boxWidth: 8,
                        }
                    },
                    tooltip: {
                        ...tooltipConfig,
                        callbacks: {
                            label: function (context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? (context.parsed / total * 100).toFixed(1) : 0;
                                return context.label + ': ' + formatNumber(context.parsed) + ' (' + percentage + '%)';
                            }
                        }
                    }
                }
            }
        });
    }

    // ================================================================ //
    // 4. Doughnut نقش‌ها (با هزینه سایت)
    // ================================================================ //
    const rolesDoughnutCanvas = document.getElementById('rolesDoughnutChart');
    if (rolesDoughnutCanvas) {
        const ctx = rolesDoughnutCanvas.getContext('2d');

        const labels = chartData.rolesChartLabels || [];
        const data = chartData.rolesChartData || [];

        const roleColors = [
            colors.gold,       // CEO
            colors.info,       // Dev
            colors.primary,    // Publish
            colors.purple,     // Content
            colors.cyan,       // Regional
            colors.site,       // Site
        ];

        const filteredLabels = [];
        const filteredData = [];
        const filteredColors = [];

        data.forEach((value, index) => {
            if (value > 0) {
                filteredLabels.push(labels[index]);
                filteredData.push(value);
                filteredColors.push(roleColors[index] || colors.text);
            }
        });

        if (filteredData.length === 0) {
            ctx.font = '14px IRANSans, sans-serif';
            ctx.fillStyle = colors.text;
            ctx.textAlign = 'center';
            ctx.fillText('داده‌ای موجود نیست', ctx.canvas.width / 2, ctx.canvas.height / 2);
        } else {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: filteredLabels,
                    datasets: [{
                        data: filteredData,
                        backgroundColor: filteredColors,
                        borderColor: '#1f1b2d',
                        borderWidth: 3,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                color: colors.text,
                                font: { size: 11 },
                                padding: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                boxWidth: 8,
                            }
                        },
                        tooltip: {
                            ...tooltipConfig,
                            callbacks: {
                                label: function (context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? (context.parsed / total * 100).toFixed(1) : 0;
                                    return context.label + ': ' + formatNumber(context.parsed) + ' (' + percentage + '%)';
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    console.log('✅ Finance Dashboard charts initialized.');
});