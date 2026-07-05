// ==================== نمودار کلیک‌های روزانه ====================

(function() {
    'use strict';

    const clicksCanvas = document.getElementById('dailyClicksChart');
    if (!clicksCanvas) return;

    const hasData = clicksCanvas.dataset.hasdata === 'true';
    let labels = [];
    let datasets = [];

    if (hasData) {
        try {
            labels = JSON.parse(clicksCanvas.dataset.labels || '[]');
            datasets = JSON.parse(clicksCanvas.dataset.datasets || '[]');
        } catch(e) {
            console.error('خطا در پارس داده‌های نمودار کلیک:', e);
        }
    }

    if (labels.length > 0 && datasets.length > 0) {
        const hasNonZero = datasets.some(ds => ds.data.some(v => v > 0));
        if (hasNonZero) {
            const enhancedDatasets = datasets.map(ds => ({
                ...ds,
                borderWidth: 2,
                backgroundColor: ds.borderColor ? (ds.borderColor + '1A') : 'rgba(253, 86, 49, 0.1)',
                pointBackgroundColor: ds.borderColor || '#fd5631',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.3,
                fill: true
            }));

            new Chart(clicksCanvas.getContext('2d'), {
                type: 'line',
                data: { labels, datasets: enhancedDatasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#fff',
                                font: { size: 12, family: 'IRANSans, Vazir' },
                                boxWidth: 12,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(19,16,36,0.8)',
                            titleColor: '#fff',
                            bodyColor: '#9691a4',
                            borderColor: '#fd5631',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y.toLocaleString() + ' کلیک';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#9691a4',
                                stepSize: 1,
                                precision: 0,
                                font: { size: 11 }
                            },
                            title: {
                                display: true,
                                text: 'تعداد کلیک‌ها',
                                color: '#9691a4',
                                font: { size: 11 }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#9691a4',
                                maxRotation: 45,
                                minRotation: 45,
                                font: { size: 10 }
                            }
                        }
                    },
                    interaction: { mode: 'index', intersect: false }
                }
            });
        } else {
            showNoDataMessage(clicksCanvas, 'هیچ کلیکی در ۳۰ روز اخیر ثبت نشده است');
        }
    } else {
        showNoDataMessage(clicksCanvas, 'هیچ داده‌ای برای نمایش وجود ندارد');
    }

})();