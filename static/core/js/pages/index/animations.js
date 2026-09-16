// ========== تایپ‌نویسی پلتفرم‌ها با رنگ و کرسر + انیمیشن خفن عکس ==========
document.addEventListener('DOMContentLoaded', function() {
    const textElement = document.getElementById('changing-text');
    const imageElement = document.getElementById('platformHeroImage');
    const imageWrapper = imageElement ? imageElement.closest('.platform-image-wrapper') : null;

    if (!textElement) return;

    // لیست پلتفرم‌ها با مسیر عکس + رنگ glow اختصاصی
    const platforms = [
        {
            name: "بله",
            class: "platform-bale",
            image: "/static/landing/bale/bale-hero.webp",
            glow: "rgba(77, 241, 182, 0.55)"
        },
        {
            name: "ایتا",
            class: "platform-eitaa",
            image: "/static/landing/eitaa/eitaa-hero.webp",
            glow: "rgba(255, 106, 0, 0.55)"
        },
        {
            name: "روبیکا",
            class: "platform-rubika",
            image: "/static/landing/rubika/rub_hero.webp",
            glow: "rgba(122, 69, 135, 0.55)"
        },
        {
            name: "سروش پلاس",
            class: "platform-soroush",
            image: "/static/landing/sorush/sor-hero.webp",
            glow: "rgba(57, 145, 172, 0.55)"
        },
        {
            name: "تلگرام",
            class: "platform-telegram",
            image: "/static/landing/telegram/tel-hero.webp",
            glow: "rgba(2, 209, 255, 0.55)"
        },
        {
            name: "اینستاگرام",
            class: "platform-instagram",
            image: "/static/landing/instagram/insta-hero.webp",
            glow: "rgba(238, 42, 123, 0.55)"
        }
    ];

    let currentIndex = 0;
    let currentCharIndex = 0;
    let isDeleting = false;
    let typingSpeed = 180;
    let deletingSpeed = 150;
    let pauseBetweenWords = 3500;
    let timeoutId = null;
    let isImageTransitioning = false;

    // تابع برای به‌روزرسانی کلاس رنگ
    function updateColorClass() {
        const currentPlatform = platforms[currentIndex];
        textElement.className = currentPlatform.class;
    }

    // ========== انیمیشن خفن تغییر عکس ==========
    function updateImage(index) {
        if (isImageTransitioning || !imageElement) return;
        isImageTransitioning = true;

        const platform = platforms[index];
        if (!platform) {
            isImageTransitioning = false;
            return;
        }

        // ست کردن رنگ glow مخصوص پلتفرم
        if (imageWrapper) {
            imageWrapper.style.setProperty('--hero-glow-color', platform.glow);
            imageWrapper.classList.add('is-changing');
        }

        // مرحله ۱: خروج عکس فعلی
        imageElement.classList.remove('hero-enter', 'hero-enter-ready');
        imageElement.classList.add('hero-exit');

        // بعد از تمام شدن انیمیشن خروج، عکس رو عوض کن و انیمیشن ورود رو بزن
        const onExitEnd = () => {
            imageElement.removeEventListener('animationend', onExitEnd);

            // تغییر src
            imageElement.src = platform.image;

            // آماده‌سازی برای ورود
            imageElement.classList.remove('hero-exit');
            imageElement.classList.add('hero-enter-ready');

            // فورس ریفلو برای اینکه مرورگر کلاس رو ببینه
            void imageElement.offsetWidth;

            // شروع انیمیشن ورود
            imageElement.classList.remove('hero-enter-ready');
            imageElement.classList.add('hero-enter');

            const onEnterEnd = () => {
                imageElement.removeEventListener('animationend', onEnterEnd);
                imageElement.classList.remove('hero-enter');

                if (imageWrapper) {
                    imageWrapper.classList.remove('is-changing');
                }
                isImageTransitioning = false;
            };

            imageElement.addEventListener('animationend', onEnterEnd, { once: true });
        };

        imageElement.addEventListener('animationend', onExitEnd, { once: true });

        // fallback اگر animationend به هر دلیلی fire نشد
        setTimeout(() => {
            if (isImageTransitioning) {
                imageElement.classList.remove('hero-exit', 'hero-enter', 'hero-enter-ready');
                imageElement.src = platform.image;
                if (imageWrapper) imageWrapper.classList.remove('is-changing');
                isImageTransitioning = false;
            }
        }, 1400);
    }

    // تابع اصلی تایپ‌نویسی
    function typeEffect() {
        const currentPlatform = platforms[currentIndex];
        const fullText = currentPlatform.name;

        updateColorClass();

        if (isDeleting) {
            textElement.textContent = fullText.substring(0, currentCharIndex - 1);
            currentCharIndex--;

            if (currentCharIndex === 0) {
                isDeleting = false;
                currentIndex = (currentIndex + 1) % platforms.length;
                clearTimeout(timeoutId);

                // قبل از تایپ کلمه جدید، عکس رو با انیمیشن خفن عوض کن
                updateImage(currentIndex);

                setTimeout(typeEffect, 300);
                return;
            }

            timeoutId = setTimeout(typeEffect, deletingSpeed);
            return;
        }

        if (currentCharIndex < fullText.length) {
            textElement.textContent = fullText.substring(0, currentCharIndex + 1);
            currentCharIndex++;
            timeoutId = setTimeout(typeEffect, typingSpeed);
        } else {
            isDeleting = true;
            clearTimeout(timeoutId);
            timeoutId = setTimeout(typeEffect, pauseBetweenWords);
        }
    }

    // مقداردهی اولیه
    textElement.textContent = '';
    textElement.className = platforms[0].class;

    // ست کردن عکس اولیه
    if (imageElement) {
        imageElement.src = platforms[0].image;
        // رنگ glow اولیه
        if (imageWrapper) {
            imageWrapper.style.setProperty('--hero-glow-color', platforms[0].glow);
        }
    }

    // شروع تایپ بعد از یک مکث کوتاه
    setTimeout(() => {
        typeEffect();
    }, 500);
});

// ========== بقیه کدهای قبلی (اسکرول، شمارنده، ذرات، ...) ==========
// اسکرول انیمیشن
const revealElements = document.querySelectorAll('.scroll-reveal');
const revealOnScroll = () => revealElements.forEach(el => {
    if (el.getBoundingClientRect().top < window.innerHeight - 100) el.classList.add('revealed');
});
window.addEventListener('scroll', revealOnScroll);
window.addEventListener('load', revealOnScroll);

// شمارنده آمار
const observer = new IntersectionObserver((entries) => entries.forEach(entry => {
    const el = entry.target;
    if (!entry.isIntersecting) return;
    const finalNum = parseInt(el.getAttribute('data-final') || el.textContent.replace(/[^0-9]/g, ''));
    if (!el.getAttribute('data-final')) el.setAttribute('data-final', finalNum);
    if (isNaN(finalNum) || finalNum <= 0) return;
    if (el.timer) clearInterval(el.timer);
    el.textContent = '0';
    let current = 0;
    const step = finalNum / 50;
    el.timer = setInterval(() => {
        current += step;
        if (current >= finalNum) {
            el.textContent = finalNum.toLocaleString('fa-IR');
            clearInterval(el.timer);
            el.timer = null;
        } else el.textContent = Math.floor(current).toLocaleString('fa-IR');
    }, 30);
}), {threshold: 0.3});
document.querySelectorAll('.stat-number').forEach(el => observer.observe(el));

// هدر اسکرول
const header = document.querySelector('.navbar');
if (header) window.addEventListener('scroll', () => header.classList.toggle('navbar-stuck', window.scrollY > 50));

// ذرات پس‌زمینه
const particlesContainer = document.getElementById('particles');
if (particlesContainer) for (let i = 0; i < 50; i++) {
    const p = document.createElement('span');
    const size = Math.random() * 4 + 2;
    p.style.width = size + 'px';
    p.style.height = size + 'px';
    p.style.left = Math.random() * 100 + '%';
    p.style.animationDelay = Math.random() * 15 + 's';
    p.style.animationDuration = Math.random() * 10 + 10 + 's';
    particlesContainer.appendChild(p);
}

// ========== Scroll Reveal کارت‌های تولید محتوا ==========
document.addEventListener('DOMContentLoaded', function() {
    const contentCards = document.querySelectorAll('.content-card.scroll-reveal');
    const revealContentCards = () => {
        contentCards.forEach((card, i) => {
            if (card.getBoundingClientRect().top < window.innerHeight - 100) {
                setTimeout(() => card.classList.add('revealed'), i * 120);
            }
        });
    };
    window.addEventListener('scroll', revealContentCards);
    window.addEventListener('load', revealContentCards);
});

// ========== انیمیشن بخش هوش مصنوعی ==========
(function() {
    'use strict';

    // ────── Counter روی اعداد ──────
    const aiCounters = document.querySelectorAll('[data-ai-count]');
    if (aiCounters.length) {
        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const el = entry.target;
                const target = parseInt(el.dataset.aiCount);
                const suffix = el.dataset.aiSuffix || '';
                const prefix = el.dataset.aiPrefix || '';
                if (!target || target <= 0) return;

                let current = 0;
                const step = Math.max(1, Math.ceil(target / 60));
                const interval = setInterval(() => {
                    current += step;
                    if (current >= target) {
                        current = target;
                        clearInterval(interval);
                    }
                    el.textContent = prefix + current.toLocaleString('fa-IR') + suffix;
                }, 25);
                counterObserver.unobserve(el);
            });
        }, { threshold: 0.4 });
        aiCounters.forEach(el => counterObserver.observe(el));
    }

    // ────── Reveal کارت‌ها با تأخیر ──────
    const aiCards = document.querySelectorAll('.ai-feature-card[data-ai-delay]');
    if (aiCards.length) {
        const cardObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const el = entry.target;
                const delay = parseInt(el.dataset.aiDelay || 0);
                setTimeout(() => el.classList.add('revealed'), delay);
                cardObserver.unobserve(el);
            });
        }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
        aiCards.forEach(el => cardObserver.observe(el));
    }

    // ────── اگه scroll-reveal از قبل داره کار می‌کنه، این رو skip کن ──────
    // (این کد برای اطمینان از اجرای reveal توی این سکشنه)

})();