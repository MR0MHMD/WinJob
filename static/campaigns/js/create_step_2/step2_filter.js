function removeParam(event, ...params) {
    event.preventDefault();
    const url = new URL(window.location.href);
    params.forEach(p => url.searchParams.delete(p));
    window.location.href = url.toString();
}

(function() {
    // تبدیل اعداد فارسی به انگلیسی
    function toEnglishDigits(str) {
        if (!str) return '';
        const map = { '۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9' };
        return str.replace(/[۰-۹]/g, ch => map[ch]);
    }

    // فقط ارقام رو نگه دار
    function getDigits(str) {
        return toEnglishDigits(str).replace(/[^\d]/g, '');
    }

    // فرمت با کاما (مثلاً "1234" -> "1,234")
    function formatWithCommas(digits) {
        if (!digits) return '';
        return parseInt(digits, 10).toLocaleString('en-US');
    }

    // مدیریت هر فیلد
    function setupLiveFormat(input) {
        if (!input) return;

        // ذخیره مقدار خالص در attribute (برای ارسال)
        let rawValue = '';

        input.addEventListener('input', function(e) {
            let cursorPos = this.selectionStart;
            let oldLength = this.value.length;
            // گرفتن ارقام خالص از مقدار فعلی
            let digits = getDigits(this.value);
            rawValue = digits;
            let formatted = formatWithCommas(digits);
            this.value = formatted;

            // تنظیم cursor برای جلوگیری از پریدن به آخر
            let newLength = this.value.length;
            let diff = newLength - oldLength;
            let newCursorPos = cursorPos + diff;
            this.setSelectionRange(newCursorPos, newCursorPos);
        });

        // قبل از ارسال فرم، مقدار raw رو در value بذار (برای سرور)
        input.form && input.form.addEventListener('submit', function() {
            let digits = getDigits(input.value);
            input.value = digits;  // عدد بدون کاما به سرور می‌ره
        });

        // مقدار اولیه رو فرمت کن
        let initDigits = getDigits(input.value);
        if (initDigits) input.value = formatWithCommas(initDigits);
    }

    // اعتبارسنجی min <= max
    function validate(minEl, maxEl, errorEl) {
        let min = getDigits(minEl.value);
        let max = getDigits(maxEl.value);
        if (min !== '' && max !== '' && parseInt(min,10) > parseInt(max,10)) {
            errorEl.style.display = 'block';
            return false;
        }
        errorEl.style.display = 'none';
        return true;
    }

    // گرفتن المان‌ها
    const followersMin = document.getElementById('followers-min-input');
    const followersMax = document.getElementById('followers-max-input');
    const priceMin = document.getElementById('price-min-input');
    const priceMax = document.getElementById('price-max-input');
    const followersError = document.getElementById('followers-range-error');
    const priceError = document.getElementById('price-range-error');

    // اعمال قالب زنده
    setupLiveFormat(followersMin);
    setupLiveFormat(followersMax);
    setupLiveFormat(priceMin);
    setupLiveFormat(priceMax);

    // اعتبارسنجی هنگام ارسال فرم مودال
    const filterForm = document.getElementById('filter-form-modal');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            let ok = true;
            if (!validate(followersMin, followersMax, followersError)) ok = false;
            if (!validate(priceMin, priceMax, priceError)) ok = false;
            if (!ok) {
                e.preventDefault();
                let firstError = document.querySelector('.invalid-feedback[style*="display: block"]');
                if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // دکمه بازنشانی
    const resetBtn = document.getElementById('modal-reset-filters');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (followersMin) followersMin.value = '';
            if (followersMax) followersMax.value = '';
            if (priceMin) priceMin.value = '';
            if (priceMax) priceMax.value = '';
            if (followersError) followersError.style.display = 'none';
            if (priceError) priceError.style.display = 'none';
            window.location.href = window.location.pathname;
        });
    }
})();