document.addEventListener('DOMContentLoaded', function () {
    // ========== ۱. وضعیت سفارش ==========
    const statusRadios = document.querySelectorAll('.status-option input[type="radio"]');
    statusRadios.forEach(radio => {
        radio.addEventListener('change', function () {
            document.querySelectorAll('.status-option').forEach(opt => opt.classList.remove('active'));
            if (this.checked) this.closest('.status-option').classList.add('active');
        });
    });

    // ========== ۲. مرتب‌سازی ==========
    const sortBtns = document.querySelectorAll('.sort-btn');
    const sortInput = document.getElementById('sortInput');
    sortBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            sortInput.value = this.dataset.sort;
            sortBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // ========== ۳. Custom Select پلتفرم ==========
    function initCustomSelect() {
        const customSelect = document.querySelector('.custom-select-wrapper');
        if (!customSelect) return;
        const trigger = customSelect.querySelector('.custom-select-trigger');
        const optionsContainer = customSelect.querySelector('.custom-options');
        const selectedText = trigger.querySelector('.selected-option-text');
        const platformInput = document.getElementById('platformInput');

        const setSelected = (option) => {
            const value = option.dataset.value;
            const logo = option.querySelector('img')?.cloneNode(true);
            const text = option.querySelector('span:last-child')?.innerText;
            selectedText.innerHTML = '';
            if (logo) selectedText.appendChild(logo);
            selectedText.appendChild(document.createTextNode(' ' + (text || 'همه پلتفرم‌ها')));
            platformInput.value = value || '';
            customSelect.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            optionsContainer.classList.remove('open');
        };

        // مقدار اولیه
        const currentVal = platformInput.value;
        const defaultOpt = customSelect.querySelector(`.custom-option[data-value="${currentVal}"]`) ||
            customSelect.querySelector('.custom-option[data-value=""]');
        if (defaultOpt) setSelected(defaultOpt);

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.custom-options.open').forEach(opt => {
                if (opt !== optionsContainer) opt.classList.remove('open');
            });
            optionsContainer.classList.toggle('open');
        });

        customSelect.querySelectorAll('.custom-option').forEach(opt => {
            opt.addEventListener('click', () => setSelected(opt));
        });

        document.addEventListener('click', () => optionsContainer.classList.remove('open'));
    }

    initCustomSelect();

    // ========== ۴. دکمه بازنشانی ==========
    const resetBtn = document.getElementById('resetFiltersBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function (e) {
            e.preventDefault();
            // وضعیت: همه
            document.querySelectorAll('.status-option input').forEach(radio => radio.checked = false);
            const allOption = document.querySelector('.status-option:first-child input');
            if (allOption) allOption.checked = true;
            document.querySelectorAll('.status-option').forEach(opt => opt.classList.remove('active'));
            document.querySelector('.status-option:first-child').classList.add('active');

            // مرتب‌سازی: جدیدترین
            sortInput.value = 'newest';
            sortBtns.forEach(b => b.classList.remove('active'));
            document.querySelector('.sort-btn[data-sort="newest"]').classList.add('active');

            // جستجو و نوع کمپین
            document.querySelector('input[name="q"]').value = '';
            document.querySelector('select[name="free"]').value = '';

            // پلتفرم (ریست به همه)
            const defaultPlatform = document.querySelector('.custom-option[data-value=""]');
            if (defaultPlatform) {
                const platformInputEl = document.getElementById('platformInput');
                platformInputEl.value = '';
                const selectedTextSpan = document.querySelector('.custom-select-trigger .selected-option-text');
                selectedTextSpan.innerHTML = '<span>🌐 همه پلتفرم‌ها</span>';
                document.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
                defaultPlatform.classList.add('selected');
            }

            // ارسال فرم
            document.getElementById('filterForm').submit();
        });
    }
});