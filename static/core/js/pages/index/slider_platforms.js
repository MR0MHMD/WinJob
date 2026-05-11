document.addEventListener('DOMContentLoaded', () => {
    const track = document.getElementById('simpleTrack');
    const prevBtn = document.getElementById('simplePrev');
    const nextBtn = document.getElementById('simpleNext');
    const dotsContainer = document.getElementById('simpleDots');
    if (!track) return;
    const isRTL = document.documentElement.getAttribute('dir') === 'rtl' || document.body.style.direction === 'rtl';
    const slides = Array.from(document.querySelectorAll('.simple-slide'));
    const totalSlides = slides.length;
    if (!totalSlides) return;
    let currentPosition = 0, slidesPerView = 3, autoPlayInterval;
    const getSlidesPerView = () => window.innerWidth < 768 ? 1 : window.innerWidth < 1200 ? 2 : 3;
    const getMaxPosition = () => totalSlides - slidesPerView;
    const updateSlider = () => {
        const sw = slides[0].offsetWidth, gap = 25;
        const tx = isRTL ? currentPosition * (sw + gap) : -(currentPosition * (sw + gap));
        track.style.transform = `translateX(${tx}px)`;
        if (prevBtn) prevBtn.disabled = currentPosition === 0;
        if (nextBtn) nextBtn.disabled = currentPosition >= getMaxPosition();
        const dotIndex = Math.ceil(currentPosition / slidesPerView);
        document.querySelectorAll('.simple-dot').forEach((d,i) => d.classList.toggle('active', i === dotIndex));
    };
    const createDots = () => {
        if (!dotsContainer) return;
        dotsContainer.innerHTML = '';
        const total = Math.ceil(totalSlides / slidesPerView);
        for (let i = 0; i < total; i++) {
            const dot = document.createElement('div');
            dot.className = 'simple-dot' + (i === 0 ? ' active' : '');
            dot.addEventListener('click', () => { currentPosition = i * slidesPerView; updateSlider(); resetAuto(); });
            dotsContainer.appendChild(dot);
        }
    };
    const nextSlide = () => { const m = getMaxPosition(); currentPosition = currentPosition < m ? currentPosition + 1 : 0; updateSlider(); };
    const startAuto = () => { clearInterval(autoPlayInterval); autoPlayInterval = setInterval(() => { if (currentPosition < getMaxPosition()) { currentPosition++; updateSlider(); } else { currentPosition = 0; updateSlider(); } }, 2500); };
    const resetAuto = () => { clearInterval(autoPlayInterval); startAuto(); };
    if (prevBtn) prevBtn.addEventListener('click', () => { if (currentPosition > 0) { currentPosition--; updateSlider(); resetAuto(); } });
    if (nextBtn) nextBtn.addEventListener('click', () => { if (currentPosition < getMaxPosition()) { currentPosition++; updateSlider(); resetAuto(); } });
    const sliderEl = document.querySelector('.simple-slider');
    if (sliderEl) { sliderEl.addEventListener('mouseenter', () => clearInterval(autoPlayInterval)); sliderEl.addEventListener('mouseleave', startAuto); }
    slidesPerView = getSlidesPerView(); createDots(); updateSlider(); startAuto();
    let resizeTimeout;
    window.addEventListener('resize', () => { clearTimeout(resizeTimeout); resizeTimeout = setTimeout(() => { const p = slidesPerView; slidesPerView = getSlidesPerView(); if (slidesPerView !== p) { currentPosition = Math.min(currentPosition, getMaxPosition()); createDots(); } updateSlider(); }, 200); });
});