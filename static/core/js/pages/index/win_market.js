// ========== وین مارکت — انیمیشن‌ها ==========
document.addEventListener('DOMContentLoaded', function () {

    // ────── 3D Tilt روی کارت محصول ──────
    const card = document.getElementById('wmProductCard');
    if (card && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        const MAX_TILT = 10;

        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            const tiltX = (0.5 - y) * MAX_TILT;
            const tiltY = (x - 0.5) * MAX_TILT;
            card.style.transform = `rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale(1.02)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    }

    // ────── شمارش معکوس کمپین ──────
    const countdownEl = document.getElementById('wmCountdown');
    if (countdownEl) {
        const endTs = parseInt(countdownEl.dataset.end, 10);
        const toFa = (n) => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);

        if (endTs && !isNaN(endTs) && endTs > Date.now()) {
            const updateCountdown = () => {
                const diff = endTs - Date.now();
                if (diff <= 0) {
                    countdownEl.textContent = 'پایان یافت';
                    return;
                }
                const days = Math.floor(diff / 86400000);
                const hours = Math.floor((diff % 86400000) / 3600000);
                const mins = Math.floor((diff % 3600000) / 60000);

                if (days > 0) {
                    countdownEl.textContent = `${toFa(days)} روز و ${toFa(hours)} ساعت`;
                } else if (hours > 0) {
                    countdownEl.textContent = `${toFa(hours)} ساعت و ${toFa(mins)} دقیقه`;
                } else {
                    countdownEl.textContent = `${toFa(mins)} دقیقه`;
                }
            };
            updateCountdown();
            setInterval(updateCountdown, 60000);
        } else {
            // کمپین تموم شده یا تاریخ نداره — مخفی کن
            countdownEl.style.display = 'none';
        }
    }

    // ────── شمارنده آمار ──────
    const statNums = document.querySelectorAll('.wm-stat-num[data-count]');
    if (statNums.length && 'IntersectionObserver' in window) {
        const toFa = (n) => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
        const formatNum = (n) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');

        const animate = (el) => {
            const target = parseInt(el.dataset.count, 10);
            if (!target || target <= 0) {
                el.textContent = toFa('0');
                return;
            }
            const duration = 1800;
            const start = performance.now();

            const step = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.floor(target * eased);
                const plus = progress === 1 ? '+' : '';
                el.textContent = toFa(formatNum(current)) + plus;
                if (progress < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
        };

        const obs = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animate(entry.target);
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.4 });

        statNums.forEach(el => obs.observe(el));
    }
});