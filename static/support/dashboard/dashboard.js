// static/support/dashboard/dashboard.js

document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    // ================================================================ //
    // 1. گرفتن دیتا از window.CHART_DATA
    // ================================================================ //
    const chartData = window.CHART_DATA;

    // اگر دیتا وجود نداشت یا خالی بود، خارج شو
    if (!chartData || !chartData.labels || chartData.labels.length === 0) {
        console.warn('دیتای چارت موجود نیست یا خالی است.');
        return;
    }

    // ================================================================ //
    // 2. گرفتن المنت canvas
    // ================================================================ //
    const canvas = document.getElementById('statsChart');
    if (!canvas) {
        console.warn('عنوان statsChart در صفحه وجود ندارد.');
        return;
    }

    const ctx = canvas.getContext('2d');

    // ================================================================ //
    // 3. ساخت نمودار
    // ================================================================ //
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    label: 'کاربران',
                    data: chartData.users,
                    backgroundColor: 'rgba(60, 118, 242, 0.6)',
                    borderColor: '#3c76f2',
                    borderWidth: 2,
                    borderRadius: 4,
                    tension: 0.4
                },
                {
                    label: 'کمپین‌ها',
                    data: chartData.campaigns,
                    backgroundColor: 'rgba(253, 86, 49, 0.6)',
                    borderColor: '#fd5631',
                    borderWidth: 2,
                    borderRadius: 4,
                    tension: 0.4
                },
                {
                    label: 'سفارشات',
                    data: chartData.orders,
                    backgroundColor: 'rgba(7, 201, 139, 0.6)',
                    borderColor: '#07c98b',
                    borderWidth: 2,
                    borderRadius: 4,
                    tension: 0.4
                },
                {
                    label: 'تیکت‌ها',
                    data: chartData.tickets,
                    backgroundColor: 'rgba(253, 188, 49, 0.6)',
                    borderColor: '#fdbc31',
                    borderWidth: 2,
                    borderRadius: 4,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#9691a4',
                        font: {
                            size: 11,
                            family: 'IRANSans'
                        },
                        boxWidth: 12,
                        padding: 15
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255,255,255,0.05)'
                    },
                    ticks: {
                        color: '#9691a4',
                        font: {
                            size: 10,
                            family: 'IRANSans'
                        },
                        stepSize: 1
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#9691a4',
                        font: {
                            size: 10,
                            family: 'IRANSans'
                        }
                    }
                }
            }
        }
    });

});