// ========== اسکرول انیمیشن ==========
const revealElements = document.querySelectorAll('.scroll-reveal');

const revealOnScroll = () => {
    revealElements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        if (rect.top < windowHeight - 100) {
            el.classList.add('revealed');
        }
    });
};

window.addEventListener('scroll', revealOnScroll);
window.addEventListener('load', revealOnScroll);

// ========== انیمیشن شمارنده آمار (تکرار شونده بهینه) ==========
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        const el = entry.target;

        if (entry.isIntersecting) {
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
                } else {
                    el.textContent = Math.floor(current).toLocaleString('fa-IR');
                }
            }, 30);
        }
    });
}, { threshold: 0.3 });

document.querySelectorAll('.stat-number').forEach(el => observer.observe(el));

// ========== دایره‌های اینفلوئنسر (افکت hover) ==========
const influencerCircles = document.querySelectorAll('.influencer-avatar-circle');
influencerCircles.forEach(circle => {
    circle.addEventListener('click', () => {
        const influencerId = circle.dataset.id;
        if (influencerId) {
            window.location.href = `/influencer/${influencerId}/`;
        }
    });
});

// ========== هدر اسکرول ==========
const header = document.querySelector('.navbar');
if (header) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('navbar-stuck');
        } else {
            header.classList.remove('navbar-stuck');
        }
    });
}

// ========== انیمیشن پیشرفت کمپین نمایشی ==========
window.addEventListener('load', () => {
    const progressBar = document.querySelector('.demo-campaign-progress-bar');
    if (progressBar) {
        setTimeout(() => {
            progressBar.style.width = '75%';
        }, 500);
    }
});

// ذرات پس‌زمینه هیرو
const particlesContainer = document.getElementById('particles');
if (particlesContainer) {
    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('span');
        const size = Math.random() * 4 + 2;
        particle.style.width = size + 'px';
        particle.style.height = size + 'px';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 15 + 's';
        particle.style.animationDuration = Math.random() * 10 + 10 + 's';
        particlesContainer.appendChild(particle);
    }
}

// ========== اسلایدر ساده کارت به کارت (سازگار با RTL) ==========
document.addEventListener('DOMContentLoaded', function() {
    const track = document.getElementById('simpleTrack');
    const prevBtn = document.getElementById('simplePrev');
    const nextBtn = document.getElementById('simpleNext');
    const dotsContainer = document.getElementById('simpleDots');

    if (!track) {
        console.error('اسلایدر پیدا نشد!');
        return;
    }

    // تشخیص RTL بودن صفحه
    const isRTL = document.documentElement.getAttribute('dir') === 'rtl' ||
                  document.body.style.direction === 'rtl';

    console.log('جهت صفحه:', isRTL ? 'RTL' : 'LTR');

    // گرفتن همه اسلایدها
    const slides = Array.from(document.querySelectorAll('.simple-slide'));
    const totalSlides = slides.length;

    if (totalSlides === 0) {
        console.error('اسلایدی وجود ندارد!');
        return;
    }

    // تنظیمات
    let currentPosition = 0; // چندمین کارت هستیم (0, 1, 2, ...)
    let slidesPerView = 3; // تعداد کارت در هر ویو
    let autoPlayInterval;

    // محاسبه تعداد کارت در هر ویو
    function getSlidesPerView() {
        const width = window.innerWidth;
        if (width < 768) return 1;
        if (width < 1200) return 2;
        return 3;
    }

    // محاسبه حداکثر موقعیت (چند بار میتونیم حرکت کنیم)
    function getMaxPosition() {
        return totalSlides - slidesPerView;
    }

    // آپدیت موقعیت اسلایدر (با در نظر گرفتن RTL)
    function updateSlider() {
        // محاسبه عرض هر اسلاید
        const slideWidth = slides[0].offsetWidth;
        const gap = 25; // فاصله بین کارت‌ها
        let translateX;

        if (isRTL) {
            // در RTL، حرکت به سمت راست (مثبت) است
            translateX = currentPosition * (slideWidth + gap);
        } else {
            // در LTR، حرکت به سمت چپ (منفی) است
            translateX = -(currentPosition * (slideWidth + gap));
        }

        track.style.transform = `translateX(${translateX}px)`;

        updateButtons();
        updateDots();
    }

    // آپدیت وضعیت دکمه‌ها (در RTL برعکس میشه)
    function updateButtons() {
        const maxPos = getMaxPosition();

        if (prevBtn) {
            // در RTL، دکمه قبلی در سمت راست است و باید به راست بره
            prevBtn.disabled = currentPosition === 0;
        }

        if (nextBtn) {
            // در RTL، دکمه بعدی در سمت چپ است و باید به چپ بره
            nextBtn.disabled = currentPosition >= maxPos;
        }
    }

    // آپدیت دات‌ها
    function updateDots() {
        const dots = document.querySelectorAll('.simple-dot');
        const currentDotIndex = Math.ceil(currentPosition / slidesPerView);

        dots.forEach((dot, i) => {
            if (i === currentDotIndex) {
                dot.classList.add('active');
            } else {
                dot.classList.remove('active');
            }
        });
    }

    // ساخت دات‌ها
    function createDots() {
        if (!dotsContainer) return;

        const totalDots = Math.ceil(totalSlides / slidesPerView);
        dotsContainer.innerHTML = '';

        for (let i = 0; i < totalDots; i++) {
            const dot = document.createElement('div');
            dot.classList.add('simple-dot');
            if (i === 0) dot.classList.add('active');

            dot.addEventListener('click', () => {
                goToDot(i);
            });

            dotsContainer.appendChild(dot);
        }
    }

    // رفتن به دات مشخص
    function goToDot(dotIndex) {
        const newPosition = dotIndex * slidesPerView;
        if (newPosition >= 0 && newPosition <= getMaxPosition()) {
            currentPosition = newPosition;
            updateSlider();
            resetAutoPlay();
        }
    }

    // رفتن به کارت بعدی (در RTL به چپ میره)
    function nextSlide() {
        const maxPos = getMaxPosition();
        if (currentPosition < maxPos) {
            currentPosition++;
            updateSlider();
            resetAutoPlay();
        }
    }

    // رفتن به کارت قبلی (در RTL به راست میره)
    function prevSlide() {
        if (currentPosition > 0) {
            currentPosition--;
            updateSlider();
            resetAutoPlay();
        }
    }

    // اتوماتیک (هر 3 ثانیه 1 کارت جلو)
    function startAutoPlay() {
        if (autoPlayInterval) clearInterval(autoPlayInterval);
        autoPlayInterval = setInterval(() => {
            const maxPos = getMaxPosition();
            if (currentPosition < maxPos) {
                nextSlide();
            } else {
                // اگه به آخر رسید، برو به اول
                currentPosition = 0;
                updateSlider();
            }
        }, 3000);
    }

    function stopAutoPlay() {
        if (autoPlayInterval) {
            clearInterval(autoPlayInterval);
            autoPlayInterval = null;
        }
    }

    function resetAutoPlay() {
        stopAutoPlay();
        startAutoPlay();
    }

    // هندل ریسایز
    let resizeTimeout;
    function handleResize() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const newSlidesPerView = getSlidesPerView();
            if (newSlidesPerView !== slidesPerView) {
                slidesPerView = newSlidesPerView;
                const maxPos = getMaxPosition();
                if (currentPosition > maxPos) {
                    currentPosition = maxPos;
                }
                createDots();
                updateSlider();
            } else {
                updateSlider();
            }
        }, 200);
    }

    // اتصال رویدادها
    if (prevBtn) prevBtn.addEventListener('click', prevSlide);
    if (nextBtn) nextBtn.addEventListener('click', nextSlide);

    // هاور روی اسلایدر
    const sliderContainer = document.querySelector('.simple-slider');
    if (sliderContainer) {
        sliderContainer.addEventListener('mouseenter', stopAutoPlay);
        sliderContainer.addEventListener('mouseleave', startAutoPlay);
    }

    // مقداردهی اولیه
    slidesPerView = getSlidesPerView();
    createDots();

    // تنظیم اولیه موقعیت در RTL
    if (isRTL) {
        // در RTL، موقعیت اولیه باید آخرین اسلایدها باشد
        // اما ما میخواهیم از اول شروع کنیم، پس فعلاً صفر足够了
        currentPosition = 0;
    }

    updateSlider();
    startAutoPlay();

    window.addEventListener('resize', handleResize);

    console.log('اسلایدر با پشتیبانی RTL راه‌اندازی شد:', {
        totalSlides: totalSlides,
        slidesPerView: slidesPerView,
        maxPosition: getMaxPosition(),
        isRTL: isRTL
    });
});

// ========== اسلایدر بی‌نهایت برندها (آروم و روان) ==========
document.addEventListener('DOMContentLoaded', function() {
    const track = document.getElementById('brandsTrack');

    if (!track) {
        console.error('اسلایدر برندها پیدا نشد!');
        return;
    }

    // تشخیص RTL
    const isRTL = document.documentElement.getAttribute('dir') === 'rtl' ||
                  document.body.style.direction === 'rtl';

    // تنظیمات
    let speed = 0.3; // سرعت آروم (پیکسل بر فریم) - عدد کمتر = آروم‌تر
    let animationId = null;
    let position = 0;
    let trackWidth = 0;

    // محاسبه عرض ترک
    function updateWidths() {
        trackWidth = track.scrollWidth / 2; // نصف می‌کنیم چون دو گروه داریم
    }

    // انیمیشن بی‌نهایت
    function animate() {
        // حرکت آروم
        if (isRTL) {
            // در RTL به سمت راست حرکت کن
            position += speed;
            if (position >= trackWidth) {
                position = 0;
            }
        } else {
            // در LTR به سمت چپ حرکت کن
            position -= speed;
            if (position <= -trackWidth) {
                position = 0;
            }
        }

        // اعمال حرکت
        track.style.transform = `translateX(${position}px)`;

        // ادامه انیمیشن
        animationId = requestAnimationFrame(animate);
    }

    // استارت انیمیشن
    function startAnimation() {
        if (animationId) {
            cancelAnimationFrame(animationId);
        }

        updateWidths();

        // تنظیم موقعیت اولیه
        if (isRTL) {
            position = 0;
        } else {
            position = 0;
        }

        track.style.transform = `translateX(${position}px)`;
        animationId = requestAnimationFrame(animate);
    }

    // توقف انیمیشن (اگه بخوای)
    function stopAnimation() {
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
    }

    // ریسپانسیو
    let resizeTimeout;
    function handleResize() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const wasPlaying = animationId !== null;
            stopAnimation();
            updateWidths();
            position = 0;
            if (wasPlaying) {
                startAnimation();
            }
        }, 250);
    }

    // هاور روی اسلایدر - آرومتر شدن (اختیاری)
    const container = document.querySelector('.brands-ticker-container');
    let originalSpeed = speed;

    if (container) {
        container.addEventListener('mouseenter', () => {
            // با هاور، سرعت رو کم‌تر کن (آروم‌تر)
            speed = originalSpeed * 0.3;
        });

        container.addEventListener('mouseleave', () => {
            // برگشت به سرعت اصلی
            speed = originalSpeed;
        });
    }
});

const platforms = [
    { name: "تلگرام", class: "platform-telegram" },
    { name: "بله", class: "platform-bale" },
    { name: "ایتا", class: "platform-eitaa" },
    { name: "روبیکا", class: "platform-rubika" },
    { name: "اینستاگرام", class: "platform-instagram" },
    { name: "سروش پلاس", class: "platform-soroush" }
];

let index = 0;
const textElement = document.getElementById("changing-text");

function changeText() {
    index = (index + 1) % platforms.length;
    textElement.style.opacity = "0";
    setTimeout(() => {
        // حذف کلاس‌های قبلی
        textElement.className = "";
        // اضافه کردن کلاس جدید مخصوص پلتفرم
        textElement.classList.add(platforms[index].class);
        textElement.textContent = platforms[index].name;
        textElement.style.opacity = "1";
    }, 200);
}

// اجرای اولیه برای تنظیم کلاس درست روی اولین متن
textElement.classList.add(platforms[0].class);
textElement.textContent = platforms[0].name;

setInterval(changeText, 4000);