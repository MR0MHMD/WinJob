function removeParam(event, ...params) {
    event.preventDefault();
    const url = new URL(window.location.href);
    params.forEach(p => url.searchParams.delete(p));
    window.location.href = url.toString();
}
(function () {
    // ---- helpers ----
    function fmt(n) {
        return Number(n).toLocaleString('fa-IR');
    }

    function initSlider(sliderId, minInputId, maxInputId,
                        minDisplayId, maxDisplayId, btnLabelId) {
        const wrap = document.getElementById(sliderId);
        if (!wrap) return;

        const min       = +wrap.dataset.min;
        const max       = +wrap.dataset.max;
        const startMin  = +wrap.dataset.startMin;
        const startMax  = +wrap.dataset.startMax;
        const step      = +wrap.dataset.step;

        const slider = noUiSlider.create(wrap, {
            start:     [startMin, startMax],
            connect:   true,
            direction: 'rtl',
            range:     { min, max },
            step,
        });

        slider.on('update', function (values) {
        // در RTL: values[0] = سمت راست (از)، values[1] = سمت چپ (تا)
        const lo = Math.round(values[0]);  // از (راست)
        const hi = Math.round(values[1]);  // تا (چپ)

        document.getElementById(minInputId).value   = lo;
        document.getElementById(maxInputId).value   = hi;
        document.getElementById(minDisplayId).textContent = fmt(lo);
        document.getElementById(maxDisplayId).textContent = fmt(hi);

        // آپدیت لیبل دکمه
        if (lo === min && hi === max) {
            document.getElementById(btnLabelId).textContent = 'همه';
        } else {
            document.getElementById(btnLabelId).textContent =
                fmt(lo) + ' – ' + fmt(hi);
        }
    });

    }

    // ---- toggle panels ----
    function togglePanel(btnId, panelId, sliderId, minInputId, maxInputId,
                         minDisplayId, maxDisplayId, btnLabelId) {
        const btn   = document.getElementById(btnId);
        const panel = document.getElementById(panelId);
        if (!btn || !panel) return;

        btn.addEventListener('click', function () {
            const isOpen = panel.style.display !== 'none';
            // بستن همه پنل‌ها
            document.querySelectorAll('.dropdown-panel')
                    .forEach(p => p.style.display = 'none');
            if (!isOpen) {
                panel.style.display = 'block';
                // اسلایدر رو فقط یه بار init کن
                const wrap = document.getElementById(sliderId);
                if (wrap && !wrap.noUiSlider) {
                    initSlider(sliderId, minInputId, maxInputId,
                               minDisplayId, maxDisplayId, btnLabelId);
                }
            }
        });
    }

    togglePanel(
        'filter-followers-toggle', 'followers-slider-panel',
        'followers-slider',
        'followers-min-input', 'followers-max-input',
        'followers-min-display', 'followers-max-display',
        'followers-btn-label'
    );

    togglePanel(
        'filter-price-toggle', 'price-slider-panel',
        'price-slider',
        'price-min-input', 'price-max-input',
        'price-min-display', 'price-max-display',
        'price-btn-label'
    );

    // ---- removeParam helper ----
    window.removeParam = function (e) {
        e.preventDefault();
        const params = new URLSearchParams(window.location.search);
        for (let i = 1; i < arguments.length; i++) params.delete(arguments[i]);
        window.location.search = params.toString();
    };

    // اگه فیلتر اسلایدر از قبل فعال بود، پنل رو باز نگه‌دار
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('followers_min') || urlParams.get('followers_max')) {
        document.getElementById('followers-slider-panel').style.display = 'block';
        initSlider('followers-slider','followers-min-input','followers-max-input',
                   'followers-min-display','followers-max-display','followers-btn-label');
    }
    if (urlParams.get('price_min') || urlParams.get('price_max')) {
        document.getElementById('price-slider-panel').style.display = 'block';
        initSlider('price-slider','price-min-input','price-max-input',
                   'price-min-display','price-max-display','price-btn-label');
    }
})();
