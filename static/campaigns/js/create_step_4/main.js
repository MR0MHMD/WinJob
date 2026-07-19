// campaigns/static/campaigns/js/create_step_4/step4_main.js

document.addEventListener('DOMContentLoaded', function() {
    // ========== ۱. دریافت مقادیر از window ==========
    // این مقادیر در تمپلیت مقداردهی میشن
    const csrfToken = window.CSRF_TOKEN || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const applyUrl = window.APPLY_DISCOUNT_URL || '/campaigns/campaign_create_step4/apply_discount';

    const existingScopes = window.EXISTING_SCOPES || {
        influencer: false,
        content_team: false,
        platform: false
    };

    // ========== ۲. مقداردهی سیستم تخفیف ==========
    if (typeof initDiscountSystem === 'function') {
        const discountSystem = initDiscountSystem(csrfToken, applyUrl, existingScopes);
    }

    // ========== ۳. مقداردهی سیستم پرداخت ==========
    if (typeof initPaymentSystem === 'function') {
        initPaymentSystem();
    }

    console.log('✅ استپ ۴ با موفقیت مقداردهی شد');
});