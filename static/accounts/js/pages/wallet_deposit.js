/**
 * صفحه شارژ کیف پول - اسکریپت‌های اختصاصی
 * با قابلیت جداسازی سه رقم سه رقم با کاما
 */

(function() {
    'use strict';

    // دکمه‌های ریست
    const resetBtn = document.getElementById('resetAmount');
    let amountInput = document.getElementById('chargeAmount');

    // تابع تبدیل عدد به فرمت با کاما
    function formatNumberWithCommas(num) {
        // حذف همه کاماهای موجود
        let cleanNum = num.toString().replace(/,/g, '');
        // تبدیل به عدد
        let number = parseFloat(cleanNum);
        // اگر عدد معتبر نبود برگردون خالی
        if (isNaN(number)) return '';
        // جداسازی با کاما
        return number.toLocaleString('en-US');
    }

    // تابع تبدیل فرمت با کاما به عدد خالص
    function cleanNumberFromCommas(formattedNum) {
        return formattedNum.replace(/,/g, '');
    }

    // هندلر برای وقتی کاربر تایپ میکنه
    function handleAmountInput(e) {
        let input = e.target;
        let cursorPosition = input.selectionStart;
        let oldValue = input.value;

        // حذف همه کاراکترهای غیر عددی (به جز کاما - ولی کاما رو هم بعداً حذف میکنیم)
        let rawValue = oldValue.replace(/[^0-9]/g, '');

        if (rawValue === '') {
            input.value = '';
            return;
        }

        // تبدیل به عدد و فرمت با کاما
        let number = parseInt(rawValue, 10);
        let formattedValue = number.toLocaleString('en-US');

        // محاسبه موقعیت جدید کرسر
        let newCursorPosition = cursorPosition;
        if (oldValue.length !== formattedValue.length) {
            // اگه کاما اضافه شده، موقعیت کرسر رو یکی جلو ببر
            if (formattedValue.length > oldValue.length) {
                newCursorPosition = cursorPosition + 1;
            }
            // اگه کاما حذف شده، موقعیت کرسر رو یکی عقب ببر
            else if (formattedValue.length < oldValue.length) {
                newCursorPosition = cursorPosition - 1;
            }
        }

        // مقدار جدید رو توی اینپوت بذار
        input.value = formattedValue;

        // موقعیت کرسر رو تنظیم کن
        if (newCursorPosition >= 0 && newCursorPosition <= formattedValue.length) {
            input.setSelectionRange(newCursorPosition, newCursorPosition);
        }
    }

    // تابع دریافت مقدار خالص (بدون کاما) برای ارسال به سرور
    function getRawAmount() {
        if (!amountInput) return '';
        return cleanNumberFromCommas(amountInput.value);
    }

    // تابع تنظیم مقدار با فرمت کاما
    function setAmountWithFormat(amount) {
        if (!amountInput) return;
        let cleanAmount = amount.toString().replace(/,/g, '');
        let number = parseInt(cleanAmount, 10);
        if (!isNaN(number)) {
            amountInput.value = number.toLocaleString('en-US');
            // اعتبارسنجی رو چک کن
            const event = new Event('input', { bubbles: true });
            amountInput.dispatchEvent(event);
        }
    }

    // هندلر کلیک روی دکمه‌های مقادیر آماده
    const presetBtns = document.querySelectorAll('.preset-btn');
    console.log('تعداد دکمه‌های پیشفرض پیدا شد:', presetBtns.length);

    presetBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const amount = this.getAttribute('data-amount');
            console.log('مبلغ انتخاب شده:', amount);

            if (amount && amountInput) {
                // مقدار رو با فرمت کاما توی اینپوت قرار بده
                let number = parseInt(amount, 10);
                amountInput.value = number.toLocaleString('en-US');

                // یه افکت خفن که نشون بده مقدار اضافه شد
                amountInput.style.transform = 'scale(1.02)';
                amountInput.style.borderColor = '#07c98b';
                amountInput.style.backgroundColor = 'rgba(7, 201, 139, 0.1)';

                // برگردوندن به حالت عادی بعد از نیم ثانیه
                setTimeout(() => {
                    amountInput.style.transform = '';
                    amountInput.style.borderColor = '';
                    amountInput.style.backgroundColor = '';
                }, 300);

                // فوکوس روی اینپوت
                amountInput.focus();

                // اعتبارسنجی رو چک کن
                const event = new Event('input', { bubbles: true });
                amountInput.dispatchEvent(event);

                // افکت خفن روی دکمه
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 150);
            }
        });
    });

    // دکمه ریست
    if (resetBtn) {
        resetBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (amountInput) {
                amountInput.value = '';
                amountInput.focus();

                // رزت استایل
                amountInput.style.borderColor = '';
                amountInput.style.backgroundColor = '';
            }
        });
    }

    // اضافه کردن event listener برای اینپوت
    if (amountInput) {
        // برای تایپ کاربر
        amountInput.addEventListener('input', handleAmountInput);

        // برای وقتی اینپوت فوکوس رو از دست میده (اعتبارسنجی نهایی)
        amountInput.addEventListener('blur', function() {
            let value = this.value;
            if (value === '') return;

            let cleanValue = cleanNumberFromCommas(value);
            let number = parseInt(cleanValue, 10);

            if (!isNaN(number)) {
                if (number < 1000) {
                    this.setCustomValidity('حداقل مبلغ ۱,۰۰۰ تومان است');
                    this.classList.add('is-invalid');
                } else if (number > 50000000) {
                    this.setCustomValidity('حداکثر مبلغ ۵۰,۰۰۰,۰۰۰ تومان است');
                    this.classList.add('is-invalid');
                } else {
                    this.setCustomValidity('');
                    this.classList.remove('is-invalid');
                }
                // دوباره فرمت کن (برای مواقعی که کاربر عدد بدون کاما وارد کرده)
                this.value = number.toLocaleString('en-US');
            }
        });

        // اعتبارسنجی لحظه‌ای
        amountInput.addEventListener('invalid', function(e) {
            e.preventDefault();
            if (this.value === '') {
                this.setCustomValidity('لطفاً مبلغ را وارد کنید');
            }
        });
    }

    // override کردن submit برای ارسال مقدار بدون کاما
    const form = document.querySelector('#chargeForm');
    const submitBtn = document.querySelector('#submitCharge');

    if (form && submitBtn) {
        form.addEventListener('submit', function(e) {
            // دریافت مقدار خالص بدون کاما
            let rawAmount = getRawAmount();
            let amountValue = parseInt(rawAmount, 10);

            // اعتبارسنجی
            if (!rawAmount || rawAmount === '' || isNaN(amountValue)) {
                e.preventDefault();
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('خطا در شارژ', 'لطفاً مبلغ را وارد کنید', 'error');
                } else {
                    alert('لطفاً مبلغ را وارد کنید');
                }
                return;
            }

            if (amountValue < 1000) {
                e.preventDefault();
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('خطا در شارژ', 'حداقل مبلغ قابل شارژ ۱,۰۰۰ تومان است', 'error');
                } else {
                    alert('حداقل مبلغ قابل شارژ ۱,۰۰۰ تومان است');
                }
                return;
            }

            if (amountValue > 50000000) {
                e.preventDefault();
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('خطا در شارژ', 'حداکثر مبلغ قابل شارژ ۵۰,۰۰۰,۰۰۰ تومان است', 'error');
                } else {
                    alert('حداکثر مبلغ قابل شارژ ۵۰,۰۰۰,۰۰۰ تومان است');
                }
                return;
            }

            // ایجاد یک hidden input برای ارسال مقدار خالص
            let hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'amount';
            hiddenInput.value = rawAmount;

            // حذف اینپوت اصلی (که مقدار با کاما داره) و اضافه کردن hidden input
            amountInput.name = '';
            form.appendChild(hiddenInput);

            // ذخیره متن اصلی دکمه
            const originalText = submitBtn.innerHTML;

            // تغییر دکمه به حالت لودینگ
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> در حال پردازش...';
            submitBtn.disabled = true;

            // اجازه بده فرم سابمیت بشه
            return true;
        });
    }

    // تابع کمکی برای تنظیم مقدار از بیرون
    window.setAmountWithFormat = setAmountWithFormat;

    console.log('صفحه شارژ کیف پول آماده است 🚀');
})();