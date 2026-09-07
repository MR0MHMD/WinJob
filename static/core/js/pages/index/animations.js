// ========== تایپ‌نویسی پلتفرم‌ها با رنگ و کرسر + عکس ساده ==========
document.addEventListener('DOMContentLoaded', function() {
    const textElement = document.getElementById('changing-text');
    const imageElement = document.getElementById('platformHeroImage');

    if (!textElement) return;

    // لیست پلتفرم‌ها با مسیر عکس
    const platforms = [
        {
            name: "بله",
            class: "platform-bale",
            image: "/static/landing/bale/bale-hero.webp",
        },
        {
            name: "ایتا",
            class: "platform-eitaa",
            image: "/static/landing/eitaa/eitaa-hero.webp",
        },
        {
            name: "روبیکا",
            class: "platform-rubika",
            image: "/static/landing/rubika/rub-hero.webp",
        },
        {
            name: "سروش پلاس",
            class: "platform-soroush",
            image: "/static/landing/sorush/sor-hero.webp",
        },
        {
            name: "تلگرام",
            class: "platform-telegram",
            image: "/static/landing/telegram/tel-hero.webp",
        },
        {
            name: "اینستاگرام",
            class: "platform-instagram",
            image: "/static/landing/instagram/insta-hero.webp",
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

    // تابع برای تغییر عکس با افکت محو ساده
    function updateImage(index) {
        if (isImageTransitioning) return;
        isImageTransitioning = true;

        const platform = platforms[index];
        if (!platform || !imageElement) return;

        // محو شدن
        imageElement.classList.add('fade-transition');

        setTimeout(() => {
            // تغییر عکس
            imageElement.src = platform.image;
            // نمایش دوباره
            imageElement.classList.remove('fade-transition');
            isImageTransitioning = false;
        }, 350);
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

                // قبل از تایپ کلمه جدید، عکس رو عوض کن
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