/**
 * صفحه شارژ کیف پول - اسکریپت‌های اختصاصی
 * طراحی جدید و خفن
 */

(function() {
    'use strict';

    // ========== المنت‌ها ==========
    const form = document.getElementById('chargeForm');
    const amountInput = document.getElementById('chargeAmount');
    const submitBtn = document.getElementById('submitCharge');
    const resetBtn = document.getElementById('resetAmount');
    const presetBtns = document.querySelectorAll('.preset-btn-new');
    const feedback = document.getElementById('amountFeedback');
    const card = document.getElementById('depositCard');

    // ========== تنظیمات ==========
    const MIN_AMOUNT = 100000;
    const MAX_AMOUNT = 50000000;

    // ========== توابع کمکی ==========
    function cleanNumber(value) {
        return String(value).replace(/,/g, '').trim();
    }

    function toNumber(value) {
        const cleaned = cleanNumber(value);
        if (cleaned === '') return NaN;
        return parseInt(cleaned, 10);
    }

    function formatWithCommas(num) {
        if (isNaN(num) || num === null || num === undefined) return '';
        return num.toLocaleString('en-US');
    }

    function showError(message) {
        amountInput.classList.add('is-invalid');
        feedback.textContent = message;
        feedback.classList.add('show');
    }

    function clearError() {
        amountInput.classList.remove('is-invalid');
        feedback.classList.remove('show');
        feedback.textContent = '';
    }

    function shakeCard() {
        card.classList.remove('shake');
        void card.offsetHeight;
        card.classList.add('shake');
        setTimeout(() => card.classList.remove('shake'), 500);
    }

    function validateAmount(value) {
        const num = toNumber(value);
        if (value === '' || value === null || value === undefined) {
            return { valid: false, message: 'لطفاً مبلغ مورد نظر را وارد کنید' };
        }
        if (isNaN(num)) {
            return { valid: false, message: 'لطفاً یک عدد معتبر وارد کنید' };
        }
        if (num < MIN_AMOUNT) {
            return { valid: false, message: `حداقل مبلغ ${formatWithCommas(MIN_AMOUNT)} تومان است` };
        }
        if (num > MAX_AMOUNT) {
            return { valid: false, message: `حداکثر مبلغ ${formatWithCommas(MAX_AMOUNT)} تومان است` };
        }
        return { valid: true, value: num };
    }

    // ========== رویدادها ==========

    // تایپ کاربر
    amountInput.addEventListener('input', function(e) {
        const raw = this.value.replace(/[^0-9]/g, '');
        if (raw === '') {
            this.value = '';
            clearError();
            return;
        }
        const num = parseInt(raw, 10);
        this.value = formatWithCommas(num);
        const result = validateAmount(this.value);
        if (!result.valid) {
            showError(result.message);
        } else {
            clearError();
        }
    });

    // فوکوس
    amountInput.addEventListener('blur', function() {
        if (this.value === '') {
            clearError();
            return;
        }
        const result = validateAmount(this.value);
        if (!result.valid) {
            showError(result.message);
        } else {
            clearError();
            this.value = formatWithCommas(result.value);
        }
    });

    // جلوگیری از ورود غیرعددی
    amountInput.addEventListener('keydown', function(e) {
        const key = e.key;
        if (['Backspace', 'Delete', 'Tab', 'Escape', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(key)) {
            return;
        }
        if (!/^[0-9]$/.test(key)) {
            e.preventDefault();
        }
    });

    // Paste
    amountInput.addEventListener('paste', function(e) {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text');
        const cleaned = text.replace(/[^0-9]/g, '');
        if (cleaned) {
            const num = parseInt(cleaned, 10);
            if (!isNaN(num)) {
                this.value = formatWithCommas(num);
                this.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    });

    // دکمه‌های پیشنهادی
    presetBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const amount = this.dataset.amount;
            const num = parseInt(amount, 10);
            if (isNaN(num)) return;

            amountInput.value = formatWithCommas(num);
            clearError();

            this.style.transform = 'scale(0.92)';
            setTimeout(() => { this.style.transform = ''; }, 150);

            amountInput.style.transform = 'scale(1.02)';
            amountInput.style.borderColor = '#07c98b';
            amountInput.style.backgroundColor = 'rgba(7, 201, 139, 0.05)';
            setTimeout(() => {
                amountInput.style.transform = '';
                amountInput.style.borderColor = '';
                amountInput.style.backgroundColor = '';
            }, 300);

            amountInput.focus();
        });
    });

    // دکمه ریست
    resetBtn.addEventListener('click', function(e) {
        e.preventDefault();
        amountInput.value = '';
        clearError();
        amountInput.focus();
        amountInput.style.borderColor = '';
        amountInput.style.backgroundColor = '';
    });

    // سابمیت
    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const result = validateAmount(amountInput.value);

        if (!result.valid) {
            showError(result.message);
            amountInput.focus();
            shakeCard();
            return;
        }

        const cleanAmount = result.value;

        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            در حال اتصال به درگاه...
        `;

        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'amount';
        hiddenInput.value = String(cleanAmount);
        amountInput.name = '';
        amountInput.disabled = true;
        form.appendChild(hiddenInput);

        try {
            form.submit();
        } catch (error) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
            amountInput.disabled = false;
            amountInput.name = 'amount';
            hiddenInput.remove();
            showError('خطا در ارسال درخواست، لطفاً مجدداً تلاش کنید');
            shakeCard();
        }
    });

    console.log('🚀 صفحه شارژ کیف پول با طراحی جدید بارگذاری شد!');
    console.log(`💰 محدوده مجاز: ${formatWithCommas(MIN_AMOUNT)} - ${formatWithCommas(MAX_AMOUNT)} تومان`);

})();