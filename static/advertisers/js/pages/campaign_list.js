document.addEventListener("DOMContentLoaded", function () {

    const filterItems = document.querySelectorAll(".filter-item");
    const campaignList = document.getElementById("campaign-list");

    filterItems.forEach(item => {

        item.addEventListener("click", function (e) {

            e.preventDefault();

            const url = this.getAttribute("href");

            fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
                .then(res => res.json())
                .then(data => {

                    campaignList.innerHTML = data.html;

                    filterItems.forEach(i => i.classList.remove("active"));
                    this.classList.add("active");

                    window.history.pushState({}, "", url);
                });
        });
    });
});

document.addEventListener('DOMContentLoaded', function () {
    // ========== مدیریت dropdownهای سفارشی ==========
    function initCustomSelect(selector) {
        const wrappers = document.querySelectorAll(selector);
        wrappers.forEach(wrapper => {
            const trigger = wrapper.querySelector('.custom-select-trigger');
            const optionsContainer = wrapper.querySelector('.custom-options');
            const selectedText = trigger.querySelector('.selected-option-text');
            const hiddenInput = wrapper.parentElement.querySelector('input[type="hidden"]');
            if (!hiddenInput) return;

            // بستن سایر dropdownها
            const closeOthers = () => {
                document.querySelectorAll('.custom-options.open').forEach(opt => {
                    if (opt !== optionsContainer) opt.classList.remove('open');
                });
            };

            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                closeOthers();
                optionsContainer.classList.toggle('open');
            });

            wrapper.querySelectorAll('.custom-option').forEach(opt => {
                opt.addEventListener('click', () => {
                    const value = opt.dataset.value;
                    const logo = opt.querySelector('img')?.cloneNode(true);
                    const text = opt.querySelector('span:last-child')?.innerText;
                    selectedText.innerHTML = '';
                    if (logo) selectedText.appendChild(logo);
                    selectedText.appendChild(document.createTextNode(' ' + (text || 'همه')));
                    hiddenInput.value = value || '';
                    wrapper.querySelectorAll('.custom-option').forEach(o => o.classList.remove('selected'));
                    opt.classList.add('selected');
                    optionsContainer.classList.remove('open');
                });
            });
        });
    }

    initCustomSelect('.custom-select-wrapper');

    // ========== مدیریت مرتب‌سازی ==========
    const sortBtns = document.querySelectorAll('.sort-btn');
    const sortInput = document.getElementById('sortInput');
    sortBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            sortInput.value = this.dataset.sort;
            sortBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // ========== دکمه بازنشانی ==========
    const resetBtn = document.getElementById('resetCampaignFiltersBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function (e) {
            e.preventDefault();
            // پاک کردن فیلدهای متنی
            document.querySelector('input[name="q"]').value = '';
            // ریست selectهای معمولی
            document.querySelectorAll('.styled-select').forEach(sel => sel.value = '');
            // ریست dropdownهای سفارشی
            document.querySelectorAll('.custom-select-wrapper').forEach(wrap => {
                const defaultOpt = wrap.querySelector('.custom-option[data-value=""]');
                if (defaultOpt) {
                    const hidden = wrap.parentElement.querySelector('input[type="hidden"]');
                    if (hidden) hidden.value = '';
                    const selectedText = wrap.querySelector('.custom-select-trigger .selected-option-text');
                    const defaultText = defaultOpt.querySelector('span:last-child')?.innerText || 'همه';
                    selectedText.innerHTML = defaultText;
                    wrap.querySelectorAll('.custom-option').forEach(o => o.classList.remove('selected'));
                    defaultOpt.classList.add('selected');
                }
            });
            // ریست مرتب‌سازی به جدیدترین
            sortInput.value = 'newest';
            sortBtns.forEach(b => b.classList.remove('active'));
            document.querySelector('.sort-btn[data-sort="newest"]').classList.add('active');
            // ارسال فرم
            document.getElementById('filterCampaignForm').submit();
        });
    }
});
