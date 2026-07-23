function initDiscountSystem(csrfToken, applyUrl, existingScopes) {
    const uniInput = document.getElementById('uni-discount-input');
    const uniBtn = document.getElementById('uni-discount-apply');

    if (!uniInput || !uniBtn) return;

    const scopeMeta = {
        influencer: {label: 'اینفلوئنسر', icon: '🌟'},
        content_team: {label: 'تیم محتوا', icon: '🎬'},
        platform: {label: 'پلتفرم', icon: '🏷️'}
    };

    let appliedScopes = existingScopes || {
        influencer: false,
        content_team: false,
        platform: false
    };

    // تابع افزودن بج تخفیف
    function addAppliedBadge(scope, code, meta) {
        const container = document.getElementById('applied-discounts-list');
        if (!container) return;

        const badge = document.createElement('div');
        badge.className = 'applied-discount-badge';
        badge.innerHTML = `
            <span class="badge-icon">${meta[scope].icon}</span>
            <span class="badge-text">${meta[scope].label}: <strong>${code}</strong></span>
            <span class="badge-remove" data-scope="${scope}">✕</span>
        `;
        container.appendChild(badge);

        badge.querySelector('.badge-remove').addEventListener('click', function() {
            console.log('حذف تخفیف برای:', scope);
        });
    }

    // تابع نمایش پیام
    function showDiscountMessage(msg, type) {
        const feedback = document.getElementById('discount-feedback');
        if (!feedback) return;

        feedback.className = `discount-message mt-2 ${type}`;
        feedback.textContent = msg;
        feedback.classList.remove('d-none');

        setTimeout(() => {
            feedback.classList.add('d-none');
        }, 5000);
    }

    // تابع غیرفعال کردن اینپوت
    function checkAndDisableUniDiscount(applied, input, btn) {
        const allApplied = Object.values(applied).every(v => v === true);
        if (allApplied) {
            input.disabled = true;
            btn.disabled = true;
            btn.textContent = 'همه تخفیف‌ها اعمال شد';
        } else {
            input.disabled = false;
            btn.disabled = false;
            btn.textContent = 'اعمال تخفیف';
        }
    }

    // تابع اصلی اعمال کد
    async function tryApplyCode(code) {
        const scopes = ['influencer', 'content_team', 'platform'];

        for (let scope of scopes) {
            if (appliedScopes[scope]) continue;

            try {
                const response = await fetch(applyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({code: code, scope: scope})
                });

                const data = await response.json();

                if (data.success) {
                    appliedScopes[scope] = true;
                    addAppliedBadge(scope, data.coupon_code, scopeMeta);

                    // *** صدا زدن تابع آپدیت از فایل helpers.js ***
                    if (typeof updateTotals === 'function') {
                        updateTotals(data);
                    }

                    showDiscountMessage(`✅ کد تخفیف ${scopeMeta[scope].label} با موفقیت اعمال شد.`, 'success');
                    uniInput.value = '';
                    uniInput.focus();
                    checkAndDisableUniDiscount(appliedScopes, uniInput, uniBtn);

                    uniBtn.disabled = true;
                    uniBtn.textContent = 'تخفیف اعمال شد';

                    return true;
                } else {
                    const errorMsg = data.message || data.error || 'خطای ناشناخته';
                    showDiscountMessage(`❌ ${errorMsg}`, 'error');

                    if (data.message && (
                        data.message.includes('قبلاً از یک کد تخفیف') ||
                        data.message.includes('قبلاً در یک کمپین دیگر')
                    )) {
                        return false;
                    }
                    continue;
                }
            } catch (e) {
                console.error('❌ خطای شبکه:', e);
                showDiscountMessage('❌ خطا در ارتباط با سرور. دوباره تلاش کنید.', 'error');
                return false;
            }
        }

        showDiscountMessage('❌ کد تخفیف معتبر نیست یا قبلاً استفاده شده است.', 'error');
        return false;
    }

    // رویدادها
    uniBtn.addEventListener('click', async function() {
        const code = uniInput.value.trim();

        if (!code) {
            showDiscountMessage('لطفاً کد تخفیف را وارد کنید.', 'error');
            return;
        }

        if (Object.values(appliedScopes).every(v => v === true)) {
            showDiscountMessage('شما قبلاً از هر سه نوع تخفیف استفاده کرده‌اید.', 'error');
            return;
        }

        uniBtn.disabled = true;
        uniBtn.textContent = 'در حال بررسی...';

        await tryApplyCode(code);

        uniBtn.disabled = false;
        if (!Object.values(appliedScopes).every(v => v === true)) {
            uniBtn.textContent = 'اعمال تخفیف';
        } else {
            uniBtn.textContent = 'همه تخفیف‌ها اعمال شد';
            uniBtn.disabled = true;
        }
    });

    uniInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            uniBtn.click();
        }
    });

    checkAndDisableUniDiscount(appliedScopes, uniInput, uniBtn);
}