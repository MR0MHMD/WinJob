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

    // مقداردهی اولیه بج‌ها
    function initExistingBadges() {
        // این توسط سرور انجام میشه و در HTML مقداردهی شده
        // فقط تابع check رو صدا میزنیم
        checkAndDisableUniDiscount(appliedScopes, uniInput, uniBtn);
    }

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
                    updateTotals(data);
                    showDiscountMessage(`✅ کد تخفیف ${scopeMeta[scope].label} با موفقیت اعمال شد.`, 'success');
                    uniInput.value = '';
                    uniInput.focus();
                    checkAndDisableUniDiscount(appliedScopes, uniInput, uniBtn);
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

    // رویداد کلیک دکمه اعمال تخفیف
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

    // Enter key
    uniInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            uniBtn.click();
        }
    });

    initExistingBadges();

    // برگرداندن توابع برای استفاده در main
    return {
        appliedScopes: appliedScopes,
        tryApplyCode: tryApplyCode,
        scopeMeta: scopeMeta
    };
}