// ========== اسلایدر نظرات برندها (3D + Swipe) – نسخه پایدار ==========
document.addEventListener('DOMContentLoaded', () => {
    const track = document.getElementById('testimonialsTrack');
    const dotsContainer = document.getElementById('testimonialsDots');

    // اگر عناصر وجود نداشتند، هیچ کاری نکن
    if (!track || !dotsContainer) return;

    const cards = Array.from(track.querySelectorAll('.testimonial-brand-card'));
    const totalCards = cards.length;

    // اگر کارتی وجود نداشت، متوقف شو
    if (totalCards === 0) return;

    let currentIndex = 0;
    let slidesPerView = getSlidesPerView();
    let autoInterval;
    let startX = 0;
    let currentTranslate = 0;
    let initialTranslate = 0;
    let isSwiping = false;

    function getSlidesPerView() {
        if (window.innerWidth <= 768) return 1;
        if (window.innerWidth <= 992) return 2;
        return 3;
    }

    function getMaxIndex() {
        return Math.max(0, totalCards - slidesPerView);
    }

    function getCardWidth() {
        return cards[0].getBoundingClientRect().width;
    }

    function getGap() {
        return window.innerWidth <= 768 ? 0 : 32; // 2rem = 32px
    }

    function updateSlider(animate = true) {
        const cardWidth = getCardWidth();
        const gap = getGap();
        const offset = -(currentIndex * (cardWidth + gap));
        track.style.transition = animate ? 'transform 0.6s cubic-bezier(0.25, 0.8, 0.25, 1.2)' : 'none';
        track.style.transform = `translateX(${offset}px)`;
        currentTranslate = offset;

        // بروزرسانی دات‌ها
        const dots = dotsContainer.querySelectorAll('.dot');
        dots.forEach((dot, idx) => {
            dot.classList.toggle('active', idx === currentIndex);
        });
    }

    function createDots() {
        dotsContainer.innerHTML = '';
        const maxIndex = getMaxIndex();
        for (let i = 0; i <= maxIndex; i++) {
            const dot = document.createElement('span');
            dot.className = 'dot' + (i === 0 ? ' active' : '');
            dot.addEventListener('click', () => {
                currentIndex = i;
                updateSlider(true);
                resetAuto();
            });
            dotsContainer.appendChild(dot);
        }
    }

    function nextSlide() {
        const maxIndex = getMaxIndex();
        currentIndex = currentIndex >= maxIndex ? 0 : currentIndex + 1;
        updateSlider(true);
    }

    function startAuto() {
        stopAuto();
        autoInterval = setInterval(nextSlide, 5000);
    }

    function stopAuto() {
        if (autoInterval) {
            clearInterval(autoInterval);
            autoInterval = null;
        }
    }

    function resetAuto() {
        stopAuto();
        startAuto();
    }

    function snapToNearest() {
        const cardWidth = getCardWidth();
        const gap = getGap();
        const totalSlideWidth = cardWidth + gap;
        let nearestIndex = Math.round(-currentTranslate / totalSlideWidth);
        nearestIndex = Math.max(0, Math.min(nearestIndex, getMaxIndex()));
        currentIndex = nearestIndex;
        updateSlider(true);
        resetAuto();
    }

    // تاچ
    track.addEventListener('touchstart', (e) => {
        if (e.touches.length !== 1) return;
        startX = e.touches[0].clientX;
        initialTranslate = currentTranslate;
        isSwiping = true;
        track.style.transition = 'none';
        stopAuto();
    }, { passive: true });

    track.addEventListener('touchmove', (e) => {
        if (!isSwiping) return;
        const currentX = e.touches[0].clientX;
        const diff = currentX - startX;
        let newTranslate = initialTranslate + diff;

        const maxTranslate = -(getMaxIndex() * (getCardWidth() + getGap()));
        const minTranslate = 0;
        if (newTranslate > minTranslate) newTranslate = minTranslate;
        if (newTranslate < maxTranslate) newTranslate = maxTranslate;

        currentTranslate = newTranslate;
        track.style.transform = `translateX(${newTranslate}px)`;
    }, { passive: true });

    track.addEventListener('touchend', () => {
        if (!isSwiping) return;
        isSwiping = false;
        snapToNearest();
    });

    // موس
    track.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startX = e.clientX;
        initialTranslate = currentTranslate;
        isSwiping = true;
        track.style.transition = 'none';
        track.style.cursor = 'grabbing';
        stopAuto();
    });

    window.addEventListener('mousemove', (e) => {
        if (!isSwiping) return;
        const diff = e.clientX - startX;
        let newTranslate = initialTranslate + diff;
        const maxTranslate = -(getMaxIndex() * (getCardWidth() + getGap()));
        const minTranslate = 0;
        if (newTranslate > minTranslate) newTranslate = minTranslate;
        if (newTranslate < maxTranslate) newTranslate = maxTranslate;
        currentTranslate = newTranslate;
        track.style.transform = `translateX(${newTranslate}px)`;
    });

    window.addEventListener('mouseup', () => {
        if (!isSwiping) return;
        isSwiping = false;
        track.style.cursor = '';
        snapToNearest();
    });

    // ریسایز
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const prevSlides = slidesPerView;
            slidesPerView = getSlidesPerView();
            if (slidesPerView !== prevSlides) {
                currentIndex = Math.min(currentIndex, getMaxIndex());
                createDots();
            }
            updateSlider(true);
        }, 200);
    });

    // استارت اولیه
    slidesPerView = getSlidesPerView();
    createDots();
    updateSlider(true);
    startAuto();

    // توقف خودکار با هاور
    const sliderEl = document.getElementById('brandTestimonialsSlider');
    if (sliderEl) {
        sliderEl.addEventListener('mouseenter', stopAuto);
        sliderEl.addEventListener('mouseleave', startAuto);
    }
});