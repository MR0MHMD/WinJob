// influencers/js/dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    const earningsCanvas = document.getElementById('dailyEarningsChart');

    if (!earningsCanvas) return;

    let labels = [];
    let values = [];

    try {
        labels = JSON.parse(earningsCanvas.dataset.labels || '[]');
        values = JSON.parse(earningsCanvas.dataset.values || '[]');
    } catch(e) {
        console.error('خطا در پارس داده‌ها:', e);
    }

    if (labels.length > 0 && values.length > 0 && values.some(v => v > 0)) {
        const ctx = earningsCanvas.getContext('2d');

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
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#07c98b',
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
                            font: { size: 12, family: 'IRANSans, Vazir' }
                        }
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
                            callback: function(value) {
                                return value.toLocaleString();
                            },
                            font: { family: 'IRANSans, Vazir', size: 11 }
                        },
                        title: {
                            display: true,
                            text: 'درآمد (تومان)',
                            color: '#9691a4',
                            font: { size: 11, family: 'IRANSans, Vazir' }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#9691a4',
                            maxRotation: 45,
                            minRotation: 45,
                            font: { family: 'IRANSans, Vazir', size: 10 }
                        }
                    }
                }
            }
        });
    } else {
        const ctx = earningsCanvas.getContext('2d');
        ctx.clearRect(0, 0, earningsCanvas.width, earningsCanvas.height);
        ctx.font = '14px IRANSans, Vazir, sans-serif';
        ctx.fillStyle = '#9691a4';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('هیچ درآمدی در ۳۰ روز اخیر ثبت نشده است', earningsCanvas.width / 2, earningsCanvas.height / 2);
    }
});