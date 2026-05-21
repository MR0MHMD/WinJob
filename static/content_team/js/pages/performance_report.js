// فایل static/js/team_report.js

document.addEventListener('DOMContentLoaded', function () {
    // داده‌ها از متغیر سراسری که در HTML تزریق شده
    const chartData = window.chartData || {};

    // ---------- نمودار روند ماهانه ----------
    const hasMonthly = (chartData.orders_count && chartData.orders_count.some(v => v > 0)) ||
        (chartData.revenue && chartData.revenue.some(v => v > 0));
    const trendCanvas = document.getElementById('trendChart');
    if (!hasMonthly) {
        const parent = trendCanvas.parentElement;
        trendCanvas.style.display = 'none';
        parent.insertAdjacentHTML('beforeend', '<div class="text-center text-muted p-5">هیچ سفارش تکمیل شده‌ای در ۶ ماه اخیر وجود ندارد</div>');
    } else {
        const ctx = trendCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.months,
                datasets: [
                    {
                        label: 'تعداد سفارشات',
                        data: chartData.orders_count,
                        type: 'bar',
                        backgroundColor: 'rgba(253, 86, 49, 0.75)',
                        borderRadius: 8,
                        barPercentage: 0.65,
                        yAxisID: 'y',
                        order: 2
                    },
                    {
                        label: 'درآمد (هزار تومان)',
                        data: chartData.revenue.map(v => Math.round(v / 1000)),
                        type: 'line',
                        borderColor: '#07c98b',
                        backgroundColor: 'rgba(7, 201, 139, 0.05)',
                        borderWidth: 3,
                        pointBackgroundColor: '#07c98b',
                        pointBorderColor: '#fff',
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'y1',
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    tooltip: {
                        mode: 'index', intersect: false, callbacks: {
                            label: (ctx) => {
                                let val = ctx.raw;
                                if (ctx.dataset.label.includes('درآمد')) return `${ctx.dataset.label}: ${(val * 1000).toLocaleString()} تومان`;
                                return `${ctx.dataset.label}: ${val.toLocaleString()}`;
                            }
                        }
                    },
                    legend: {position: 'top', labels: {color: '#fff', usePointStyle: true}},
                    animation: {duration: 1000, easing: 'easeOutQuart'}
                },
                scales: {
                    y: {
                        title: {display: true, text: 'تعداد سفارش', color: '#fd5631'},
                        ticks: {color: '#ccc', stepSize: 1},
                        grid: {color: 'rgba(255,255,255,0.05)'}
                    },
                    y1: {
                        position: 'right',
                        title: {display: true, text: 'درآمد (هزار تومان)', color: '#07c98b'},
                        ticks: {color: '#07c98b'},
                        grid: {drawOnChartArea: false}
                    },
                    x: {ticks: {color: '#aaa', rotate: 45}, grid: {display: false}}
                }
            }
        });
    }

    // ---------- نمودار دایره‌ای ----------
    const pieCanvas = document.getElementById('servicePieChart');
    if (chartData.service_labels && chartData.service_labels.length && chartData.service_counts.some(c => c > 0)) {
        const ctxPie = pieCanvas.getContext('2d');
        new Chart(ctxPie, {
            type: 'pie',
            data: {
                labels: chartData.service_labels,
                datasets: [{
                    data: chartData.service_counts,
                    backgroundColor: ['#fd5631', '#5d3cf2', '#07c98b', '#fdbc31', '#3c76f2', '#f23c49'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {position: 'bottom', labels: {color: '#fff', font: {size: 11}}},
                    tooltip: {callbacks: {label: (ctx) => `${ctx.label}: ${ctx.raw} سفارش`}}
                }
            }
        });
    } else {
        const pieParent = pieCanvas.parentElement;
        pieCanvas.style.display = 'none';
        pieParent.insertAdjacentHTML('beforeend', '<div class="text-center text-muted p-4">هیچ سفارش تکمیل شده‌ای موجود نیست</div>');
    }

    // ---------- نمودار روزانه (۱۰ روز) ----------
    const dailyCanvas = document.getElementById('dailyChart');
    const hasDaily = (chartData.daily_orders && chartData.daily_orders.some(v => v > 0)) ||
        (chartData.daily_revenue && chartData.daily_revenue.some(v => v > 0));
    if (!hasDaily) {
        const dailyParent = dailyCanvas.parentElement;
        dailyCanvas.style.display = 'none';
        dailyParent.insertAdjacentHTML('beforeend', '<div class="text-center text-muted p-5">هیچ سفارشی در ۱۰ روز اخیر تکمیل نشده است</div>');
    } else {
        const ctxDaily = dailyCanvas.getContext('2d');
        new Chart(ctxDaily, {
            type: 'line',
            data: {
                labels: chartData.daily_labels,
                datasets: [
                    {
                        label: 'تعداد سفارشات (روزانه)',
                        data: chartData.daily_orders,
                        borderColor: '#fd5631',
                        backgroundColor: 'rgba(253,86,49,0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        yAxisID: 'y'
                    },
                    {
                        label: 'درآمد روزانه (تومان)',
                        data: chartData.daily_revenue,
                        borderColor: '#07c98b',
                        backgroundColor: 'rgba(7,201,139,0.05)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    tooltip: {
                        mode: 'index', intersect: false, callbacks: {
                            label: (ctx) => {
                                let val = ctx.raw;
                                if (ctx.dataset.label.includes('درآمد')) return `${ctx.dataset.label}: ${val.toLocaleString()} تومان`;
                                return `${ctx.dataset.label}: ${val.toLocaleString()}`;
                            }
                        }
                    },
                    legend: {position: 'top', labels: {color: '#fff', usePointStyle: true}},
                    animation: {duration: 1000}
                },
                scales: {
                    y: {
                        title: {display: true, text: 'تعداد سفارش', color: '#fd5631'},
                        ticks: {color: '#ccc', stepSize: 1},
                        grid: {color: 'rgba(255,255,255,0.05)'}
                    },
                    y1: {
                        position: 'right',
                        title: {display: true, text: 'درآمد (تومان)', color: '#07c98b'},
                        ticks: {color: '#07c98b'},
                        grid: {drawOnChartArea: false}
                    },
                    x: {
                        ticks: {
                            color: '#aaa',
                            rotate: 45,
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 10
                        }, grid: {display: false}
                    }
                }
            }
        });
    }
});