// campaigns/static/campaigns/js/create_step_3/team/replacement-mode.js

(function() {
    'use strict';

    const IS_REPLACEMENT_MODE = window.IS_REPLACEMENT_MODE || false;
    const WALLET_BALANCE = window.WALLET_BALANCE || 0;
    const CAMPAIGN_ID = window.CAMPAIGN_ID || null;

    if (!IS_REPLACEMENT_MODE) return;

    function initReplacementMode() {
        // ========== ۱. مخفی کردن کامل بخش بریف ==========
        const briefSection = document.getElementById('brief-section');
        if (briefSection) {
            briefSection.style.display = 'none';
            briefSection.style.visibility = 'hidden';
            briefSection.style.height = '0';
            briefSection.style.overflow = 'hidden';
            briefSection.style.padding = '0';
            briefSection.style.margin = '0';
        }

        // ========== ۲. مخفی کردن کامل بخش محتوای تبلیغ ==========
        const adContentSection = document.getElementById('ad-content-section');
        if (adContentSection) {
            adContentSection.style.display = 'none';
            adContentSection.style.visibility = 'hidden';
            adContentSection.style.height = '0';
            adContentSection.style.overflow = 'hidden';
            adContentSection.style.padding = '0';
            adContentSection.style.margin = '0';
        }

        // ========== ۳. غیرفعال کردن دکمه submit به صورت پیش‌فرض ==========
        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ لطفاً یک تیم و پلن انتخاب کنید';
            submitBtn.classList.add('opacity-50');
        }

        // ========== ۴. گوش دادن به انتخاب پلن ==========
        document.addEventListener('planSelected', function(e) {
            if (submitBtn) {
                // دکمه توسط team-selection.js فعال میشه
                // اینجا فقط برای اطمینان
            }
        });

        document.addEventListener('planCleared', function() {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ لطفاً یک تیم و پلن انتخاب کنید';
                submitBtn.classList.add('opacity-50');
            }
        });

        // ========== ۵. مخفی کردن دکمه "مرحله قبل" ==========
        const prevBtn = document.querySelector('a[href*="campaign_create_step2"]');
        if (prevBtn) {
            prevBtn.style.display = 'none';
        }

        // ========== ۶. نمایش موجودی کیف پول ==========
        const walletDisplay = document.createElement('div');
        walletDisplay.className = 'alert alert-info bg-faded-info text-info mb-3 d-flex align-items-center gap-2';
        walletDisplay.innerHTML = `
            <i class="fi-wallet fs-5"></i>
            <div>
                <strong>💰 موجودی کیف پول شما:</strong>
                <span class="fw-bold">${Number(WALLET_BALANCE).toLocaleString('fa-IR')} تومان</span>
                <span class="text-muted small ms-2">(فقط تیم‌هایی که حداقل یک پلن با قیمت کمتر یا مساوی موجودی شما داشته باشند نمایش داده می‌شوند.)</span>
            </div>
        `;

        const header = document.querySelector('.replacement-header-team');
        if (header) {
            header.parentNode.insertBefore(walletDisplay, header.nextSibling);
        }

        // ========== ۷. هشدار به کاربر ==========
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-warning bg-faded-warning text-warning mb-3';
        alertDiv.innerHTML = `
            <i class="fi-info-circle me-2"></i>
            <strong>توجه:</strong> در این حالت فقط می‌توانید تیم تولید محتوای جایگزین انتخاب کنید.
            اطلاعات بریف و محتوای تبلیغ از قبل ثبت شده‌اند و قابل تغییر نیستند.
        `;

        if (header) {
            header.parentNode.insertBefore(alertDiv, walletDisplay.nextSibling);
        }

        // ========== ۸. اضافه کردن CAMPAIGN_ID به window ==========
        if (CAMPAIGN_ID) {
            window.CAMPAIGN_ID = CAMPAIGN_ID;
        }

        // ========== ۹. مخفی کردن بخش‌های اضافی با CSS ==========
        const style = document.createElement('style');
        style.textContent = `
            .replacement-mode-hidden {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                overflow: hidden !important;
                padding: 0 !important;
                margin: 0 !important;
                opacity: 0 !important;
                pointer-events: none !important;
            }
        `;
        document.head.appendChild(style);

        // اضافه کردن کلاس به بخش‌ها
        if (briefSection) briefSection.classList.add('replacement-mode-hidden');
        if (adContentSection) adContentSection.classList.add('replacement-mode-hidden');

        console.log('✅ حالت جایگزینی تیم محتوا فعال شد');
        console.log('💰 موجودی کیف پول:', WALLET_BALANCE);
        console.log('🆔 شناسه کمپین:', CAMPAIGN_ID);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReplacementMode);
    } else {
        initReplacementMode();
    }
})();