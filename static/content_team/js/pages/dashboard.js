// dashboard.js کامل اصلاح شده

document.addEventListener('DOMContentLoaded', function() {
    // نمودار درآمد ماهانه (6 ماه اخیر)
    const revenueCanvas = document.getElementById('monthlyRevenueChart');
    if (revenueCanvas) {
        let labels = [];
        let values = [];

        try {
            labels = JSON.parse(revenueCanvas.dataset.labels || '[]');
            values = JSON.parse(revenueCanvas.dataset.values || '[]');
        } catch(e) {
            console.error('خطا در پارس داده‌های درآمد:', e);
        }

        if (labels.length > 0 && values.length > 0 && values.some(v => v > 0)) {
            const ctx = revenueCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'درآمد (تومان)',
                        data: values,
                        borderColor: '#07c98b',
                        backgroundColor: 'rgba(7, 201, 139, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#07c98b',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            labels: { color: '#fff', font: { size: 12, family: 'IRANSans, Vazir' } }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            titleColor: '#fff',
                            bodyColor: '#9691a4',
                            borderColor: '#07c98b',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.parsed.y.toLocaleString() + ' تومان';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#9691a4',
                                callback: function(value) { return value.toLocaleString(); },
                                font: { family: 'IRANSans, Vazir', size: 11 }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#9691a4',
                                font: { family: 'IRANSans, Vazir', size: 11 },
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    }
                }
            });
        } else {
            showNoDataMessage(revenueCanvas, 'هیچ درآمدی در ۶ ماه اخیر ثبت نشده است');
        }
    }

    // نمودار تعداد سفارشات روزانه (30 روز اخیر)
    const ordersCanvas = document.getElementById('monthlyOrdersChart');
    if (ordersCanvas) {
        let labels = [];
        let values = [];

        try {
            labels = JSON.parse(ordersCanvas.dataset.labels || '[]');
            values = JSON.parse(ordersCanvas.dataset.values || '[]');
        } catch(e) {
            console.error('خطا در پارس داده‌های سفارشات:', e);
        }

        if (labels.length > 0 && values.length > 0) {
            // محاسبه عرض میله بر اساس تعداد داده‌های غیرصفر
            const nonZeroCount = values.filter(v => v > 0).length;
            let barPercentage = 0.6;
            let categoryPercentage = 0.8;

            // اگر داده‌های کمی داریم، عرض میله رو کمتر کن
            if (nonZeroCount <= 3) {
                barPercentage = 0.3;      // عرض میله کمتر
                categoryPercentage = 0.5;  // فاصله بین میله‌ها بیشتر
            } else if (nonZeroCount <= 7) {
                barPercentage = 0.45;
                categoryPercentage = 0.7;
            }

            const ctx = ordersCanvas.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'تعداد سفارشات',
                        data: values,
                        backgroundColor: 'rgba(253, 86, 49, 0.8)',
                        borderColor: '#fd5631',
                        borderWidth: 1,
                        borderRadius: 6,
                        barPercentage: barPercentage,      // عرض میله
                        categoryPercentage: categoryPercentage,  // فاصله بین گروه‌ها
                        maxBarThickness: 40  // حداکثر ضخامت هر میله
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            labels: { color: '#fff', font: { size: 12, family: 'IRANSans, Vazir' } }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            titleColor: '#fff',
                            bodyColor: '#9691a4',
                            borderColor: '#fd5631',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    let value = context.parsed.y;
                                    if (value === 0) return 'بدون سفارش';
                                    return value.toLocaleString() + ' سفارش';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#9691a4',
                                stepSize: 1,
                                font: { family: 'IRANSans, Vazir', size: 11 },
                                callback: function(value) {
                                    return Math.floor(value) === value ? value : null;
                                }
                            },
                            beginAtZero: true
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#9691a4',
                                font: { family: 'IRANSans, Vazir', size: 10 },
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 15
                            }
                        }
                    },
                    layout: {
                        padding: {
                            left: 10,
                            right: 10,
                            top: 20,
                            bottom: 10
                        }
                    }
                }
            });
        } else {
            showNoDataMessage(ordersCanvas, 'هیچ سفارشی در ۳۰ روز اخیر ثبت نشده است');
        }
    }

    function showNoDataMessage(canvas, message) {
        const ctx = canvas.getContext('2d');
        const container = canvas.parentElement;
        const width = canvas.width || container.clientWidth;
        const height = canvas.height || 250;

        canvas.width = width;
        canvas.height = height;

        ctx.clearRect(0, 0, width, height);
        ctx.font = '14px IRANSans, Vazir, sans-serif';
        ctx.fillStyle = '#9691a4';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(message, width / 2, height / 2);
    }
});