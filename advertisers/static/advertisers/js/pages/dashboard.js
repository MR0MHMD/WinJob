// advertisers/js/pages/dashboard.js

document.addEventListener('DOMContentLoaded', function () {

    // تابع نمایش پیام بدون داده
    function showNoDataMessage(canvas, message) {
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        ctx.clearRect(0, 0, width, height);
        ctx.font = '14px IRANSans, Vazir, sans-serif';
        ctx.fillStyle = '#9691a4';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(message || 'هیچ داده‌ای برای نمایش وجود ندارد', width / 2, height / 2);
    }

    // تابع کمکی برای دریافت داده از dataset
    function getChartData(canvas, dataName) {
        if (!canvas) return {labels: [], values: []};

        let labels = [];
        let values = [];

        try {
            labels = JSON.parse(canvas.dataset.labels || '[]');
            values = JSON.parse(canvas.dataset.values || '[]');
        } catch (e) {
            console.error('خطا در پارس داده‌های ' + dataName + ':', e);
        }

        return {labels, values};
    }

    // ========== نمودار هزینه روزانه (۳۰ روز اخیر) ==========
    const dailySpendingCanvas = document.getElementById('dailySpendingChart');

    if (dailySpendingCanvas) {
        const {labels, values} = getChartData(dailySpendingCanvas, 'هزینه روزانه');
        const ctx = dailySpendingCanvas.getContext('2d');

        if (labels.length > 0 && values.length > 0) {
            const hasNonZeroData = values.some(v => v > 0);

            if (hasNonZeroData) {
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'هزینه (تومان)',
                            data: values,
                            borderColor: '#fd5631',
                            backgroundColor: 'rgba(253, 86, 49, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointBackgroundColor: '#fd5631',
                            pointBorderColor: '#fff',
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            pointHoverBackgroundColor: '#fd5631',
                            pointHoverBorderColor: '#fff',
                            pointHoverBorderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#fff',
                                    font: {size: 12, family: 'IRANSans, Vazir'}
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleColor: '#fff',
                                bodyColor: '#9691a4',
                                borderColor: '#fd5631',
                                borderWidth: 1,
                                callbacks: {
                                    label: function (context) {
                                        return context.parsed.y.toLocaleString() + ' تومان';
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                grid: {color: 'rgba(255,255,255,0.05)'},
                                ticks: {
                                    color: '#9691a4',
                                    callback: function (value) {
                                        return value.toLocaleString();
                                    },
                                    font: {family: 'IRANSans, Vazir', size: 11}
                                },
                                title: {
                                    display: true,
                                    text: 'هزینه (تومان)',
                                    color: '#9691a4',
                                    font: {size: 11, family: 'IRANSans, Vazir'}
                                }
                            },
                            x: {
                                grid: {display: false},
                                ticks: {
                                    color: '#9691a4',
                                    maxRotation: 45,
                                    minRotation: 45,
                                    font: {family: 'IRANSans, Vazir', size: 10}
                                }
                            }
                        }
                    }
                });
            } else {
                showNoDataMessage(dailySpendingCanvas, 'هیچ هزینه‌ای در ۳۰ روز اخیر ثبت نشده است');
            }
        } else {
            showNoDataMessage(dailySpendingCanvas, 'هیچ هزینه‌ای در ۳۰ روز اخیر ثبت نشده است');
        }
    }

    // ========== نمودار کلیک‌های روزانه (۳۰ روز اخیر) ==========
    const dailyClicksCanvas = document.getElementById('dailyClicksChart');

    if (dailyClicksCanvas) {
        const {labels, values} = getChartData(dailyClicksCanvas, 'کلیک روزانه');
        const ctx = dailyClicksCanvas.getContext('2d');

        if (labels.length > 0 && values.length > 0) {
            const hasNonZeroData = values.some(v => v > 0);

            if (hasNonZeroData) {
                const maxValue = Math.max(...values);
                const stepSize = maxValue <= 10 ? 1 : (maxValue <= 50 ? 5 : (maxValue <= 100 ? 10 : 20));

                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'تعداد کلیک‌ها',
                            data: values,
                            backgroundColor: 'rgba(93, 60, 242, 0.7)',
                            borderColor: '#5d3cf2',
                            borderWidth: 1,
                            borderRadius: 2,
                            barPercentage: 0.15,
                            categoryPercentage: 0.3,
                            hoverBackgroundColor: 'rgba(93, 60, 242, 0.9)',
                            hoverBorderColor: '#5d3cf2'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#fff',
                                    font: {size: 12, family: 'IRANSans, Vazir'}
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleColor: '#fff',
                                bodyColor: '#9691a4',
                                borderColor: '#5d3cf2',
                                borderWidth: 1,
                                callbacks: {
                                    label: function (context) {
                                        return context.parsed.y.toLocaleString() + ' کلیک';
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                grid: {color: 'rgba(255,255,255,0.05)'},
                                ticks: {
                                    color: '#9691a4',
                                    stepSize: stepSize,
                                    precision: 0,
                                    font: {family: 'IRANSans, Vazir', size: 11}
                                },
                                title: {
                                    display: true,
                                    text: 'تعداد کلیک‌ها',
                                    color: '#9691a4',
                                    font: {size: 11, family: 'IRANSans, Vazir'}
                                }
                            },
                            x: {
                                grid: {display: false},
                                ticks: {
                                    color: '#9691a4',
                                    maxRotation: 45,
                                    minRotation: 45,
                                    font: {family: 'IRANSans, Vazir', size: 10}
                                }
                            }
                        }
                    }
                });
            } else {
                showNoDataMessage(dailyClicksCanvas, 'هیچ کلیکی در ۳۰ روز اخیر ثبت نشده است');
            }
        } else {
            showNoDataMessage(dailyClicksCanvas, 'هیچ کلیکی در ۳۰ روز اخیر ثبت نشده است');
        }
    }
});