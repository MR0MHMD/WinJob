document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.channels-grid').forEach(container => {
        let isDragging = false, startX, startScrollLeft, mouseMoved = false;
        container.addEventListener('mousedown', (e) => { isDragging = true; container.classList.add('active'); startX = e.pageX - container.offsetLeft; startScrollLeft = container.scrollLeft; mouseMoved = false; });
        container.addEventListener('mouseleave', () => { isDragging = false; container.classList.remove('active'); });
        container.addEventListener('mouseup', () => { isDragging = false; container.classList.remove('active'); });
        container.addEventListener('mousemove', (e) => { if (!isDragging) return; e.preventDefault(); mouseMoved = true; container.scrollLeft = startScrollLeft - (e.pageX - container.offsetLeft - startX) * 2; });
        container.addEventListener('touchstart', (e) => { startX = e.touches[0].pageX - container.offsetLeft; startScrollLeft = container.scrollLeft; }, { passive: true });
        container.addEventListener('touchmove', (e) => { container.scrollLeft = startScrollLeft - (e.touches[0].pageX - container.offsetLeft - startX) * 2; }, { passive: true });
        container.querySelectorAll('a').forEach(link => link.addEventListener('click', (e) => { if (mouseMoved) { e.preventDefault(); e.stopPropagation(); } }));
    });
});