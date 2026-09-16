// ==================== توابع نمایش مودال‌ها ====================

(function () {
    'use strict';

    // ==================== توابع کمکی داخلی ====================

    /**
     * گرفتن المان‌های مودال عمومی
     */
    function getModalElements() {
        return {
            modalElement: document.getElementById('globalNotificationModal'),
            modalTitle: document.getElementById('notificationModalTitle'),
            modalIcon: document.getElementById('notificationModalIcon'),
            modalMessage: document.getElementById('notificationModalMessage'),
            modalBtn: document.getElementById('notificationModalBtn'),
        };
    }

    /**
     * تنظیم CSRF token توی فرم
     */
    function getCsrfInput() {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = getCookie('csrftoken');
        return csrfInput;
    }

    /**
     * ارسال فرم POST
     */
    function submitPostForm(action) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = action;
        form.appendChild(getCsrfInput());
        document.body.appendChild(form);
        form.submit();
    }

    /**
     * جایگزین کردن دکمه با نسخه جدید (برای پاک کردن listener های قبلی)
     */
    function replaceButton(btn, newHtml, newClass) {
        btn.innerHTML = newHtml;
        if (newClass) btn.className = newClass;
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        return newBtn;
    }

    /**
     * بستن مودال
     */
    function closeModal(modalElement) {
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();
    }

    // ==================== تابع اصلی: ادامه بدون جایگزینی ====================

    window.showContinueWithoutReplacementModal = function (campaignId) {
        const { modalElement, modalTitle, modalIcon, modalMessage, modalBtn } = getModalElements();

        if (!modalElement) {
            console.error('❌ globalNotificationModal not found!');
            return;
        }

        // ========== دریافت اطلاعات کمپین از طریق AJAX ==========
        fetch(`/campaigns/api/campaign-tax-info/${campaignId}/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (!data.success) {
                    showContinueWithoutReplacementModalFallback(campaignId);
                    return;
                }

                const influencerCost = data.influencer_cost || 0;
                const contentCost = data.content_cost || 0;
                const commission = data.commission || 0;
                const oldVat = data.total_vat || 0;

                // ========== محاسبه هزینه ناشران جدید ==========
                const newInfluencerCost = data.new_influencer_cost || influencerCost;

                // ========== محاسبه مالیات جدید ==========
                const taxBase = newInfluencerCost + contentCost + commission;
                const newVat = Math.round(taxBase * 0.10);

                // ========== مابه‌التفاوت مالیات ==========
                const vatDiff = newVat - oldVat;
                const refundAmount = Math.abs(vatDiff);

                // ========== تنظیم عنوان و آیکون ==========
                modalTitle.innerHTML = `<i class="fi-alert-triange me-2 text-warning"></i> ادامه بدون جایگزینی`;
                modalIcon.className = 'notification-icon warning';
                modalIcon.innerHTML = `<i class="fi-alert-triange"></i>`;

                // ========== پیام برگشت پول ==========
                let refundMessage = '';
                if (refundAmount > 0) {
                    refundMessage = `
                        <div class="alert alert-success bg-faded-success text-success text-start mt-3">
                            <i class="fi-wallet me-2"></i>
                            <strong>💰 مبلغ قابل برگشت به کیف پول شما:</strong>
                            <span class="fw-bold fs-5 d-block mt-1">${refundAmount.toLocaleString('fa-IR')} تومان</span>
                            <small class="d-block mt-1">(بابت کاهش مالیات بر ارزش افزوده پس از حذف ناشران رد شده)</small>
                        </div>
                    `;
                }

                // ========== نمایش ناشران رد شده ==========
                let rejectedChannelsHtml = '';
                if (data.rejected_channels && data.rejected_channels.length > 0) {
                    rejectedChannelsHtml = `
                        <div class="mt-3">
                            <div class="text-muted small mb-2">ناشران رد شده:</div>
                            <div class="d-flex flex-wrap gap-2">
                                ${data.rejected_channels.map(ch => `
                                    <span class="badge bg-faded-danger rounded-pill px-3 py-2">
                                        <i class="fi-user me-1"></i>
                                        ${ch.channel_name}
                                        <span class="text-muted small me-1">(${ch.price.toLocaleString('fa-IR')} تومان)</span>
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }

                // ========== پیام اصلی ==========
                modalMessage.innerHTML = `
                    <div class="text-start">
                        <p class="text-light mb-3">
                            آیا از ادامه کمپین <strong class="text-warning">بدون انتخاب ناشر جایگزین</strong> مطمئن هستید؟
                        </p>
                        <div class="alert alert-warning bg-faded-warning text-warning text-start">
                            <i class="fi-info-circle me-2"></i>
                            <strong>نکته:</strong> ناشران رد شده نادیده گرفته خواهند شد و
                            <span class="text-danger fw-bold">قابل بازگشت نیستند</span>.
                            <br>
                            <span class="text-light-emphasis">هزینه ناشران رد شده قبلاً به کیف پول شما برگشت داده شده است.</span>
                        </div>
                        ${rejectedChannelsHtml}
                        ${refundMessage}
                        <p class="text-muted small mb-0 mt-3">
                            <i class="fi-clock me-1"></i>
                            در صورت انتخاب این گزینه، کمپین شما به حالت تایید شده بازمی‌گردد.
                        </p>
                    </div>
                `;

                // ========== تنظیم دکمه تأیید ==========
                const newBtn = replaceButton(
                    modalBtn,
                    `<i class="fi-check me-1"></i> بله، ادامه می‌دم`,
                    'btn btn-success rounded-pill px-4'
                );

                newBtn.addEventListener('click', function () {
                    closeModal(modalElement);
                    submitPostForm(`/campaigns/continue-without-replacement/${campaignId}/`);
                });

                // ========== نمایش مودال ==========
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
            })
            .catch(error => {
                console.error('❌ خطا در دریافت اطلاعات کمپین:', error);
                showContinueWithoutReplacementModalFallback(campaignId);
            });
    };

    // ==================== Fallback: ادامه بدون جایگزینی ====================

    function showContinueWithoutReplacementModalFallback(campaignId) {
        const { modalElement, modalTitle, modalIcon, modalMessage, modalBtn } = getModalElements();

        if (!modalElement) {
            console.error('❌ globalNotificationModal not found!');
            return;
        }

        modalTitle.innerHTML = `<i class="fi-alert-triange me-2 text-warning"></i> ادامه بدون جایگزینی`;
        modalIcon.className = 'notification-icon warning';
        modalIcon.innerHTML = `<i class="fi-alert-triange"></i>`;

        modalMessage.innerHTML = `
            <div class="text-start">
                <p class="text-light mb-3">
                    آیا از ادامه کمپین <strong class="text-warning">بدون انتخاب ناشر جایگزین</strong> مطمئن هستید؟
                </p>
                <div class="alert alert-warning bg-faded-warning text-warning text-start">
                    <i class="fi-info-circle me-2"></i>
                    <strong>نکته:</strong> ناشران رد شده نادیده گرفته خواهند شد و
                    <span class="text-danger fw-bold">قابل بازگشت نیستند</span>.
                    <br>
                    <span class="text-light-emphasis">هزینه ناشران رد شده قبلاً به کیف پول شما برگشت داده شده است.</span>
                </div>
                <p class="text-muted small mb-0 mt-3">
                    <i class="fi-clock me-1"></i>
                    در صورت انتخاب این گزینه، کمپین شما به حالت تایید شده بازمی‌گردد.
                </p>
            </div>
        `;

        const newBtn = replaceButton(
            modalBtn,
            `<i class="fi-check me-1"></i> بله، ادامه می‌دم`,
            'btn btn-success rounded-pill px-4'
        );

        newBtn.addEventListener('click', function () {
            closeModal(modalElement);
            submitPostForm(`/campaigns/continue-without-replacement/${campaignId}/`);
        });

        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }

    // ==================== تابع اصلی: تبدیل به محتوای آماده ====================

    window.showSwitchToReadyModal = function (campaignId) {
        const { modalElement, modalTitle, modalIcon, modalMessage, modalBtn } = getModalElements();

        if (!modalElement) {
            console.error('❌ globalNotificationModal not found!');
            return;
        }

        // ========== دریافت اطلاعات کمپین از طریق AJAX ==========
        fetch(`/campaigns/api/campaign-tax-info/${campaignId}/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const influencerCost = data.influencer_cost || 0;
                const commission = data.commission || 0;
                const oldVat = data.total_vat || 0;

                // ========== محاسبه مالیات جدید (بدون هزینه محتوا) ==========
                const newVat = Math.round((influencerCost + commission) * 0.10);

                // ========== مابه‌التفاوت مالیات ==========
                const vatDiff = newVat - oldVat;
                const refundAmount = Math.abs(vatDiff);

                // ========== تنظیم عنوان و آیکون ==========
                modalTitle.innerHTML = `<i class="fi-upload me-2 text-info"></i> آپلود محتوای آماده`;
                modalIcon.className = 'notification-icon info';
                modalIcon.innerHTML = `<i class="fi-info-circle"></i>`;

                // ========== پیام برگشت پول ==========
                let refundMessage = '';
                if (refundAmount > 0) {
                    refundMessage = `
                        <div class="alert alert-success bg-faded-success text-success text-start mt-3">
                            <i class="fi-wallet me-2"></i>
                            <strong>💰 مبلغ قابل برگشت به کیف پول شما:</strong>
                            <span class="fw-bold fs-5 d-block mt-1">${refundAmount.toLocaleString('fa-IR')} تومان</span>
                            <small class="d-block mt-1">(بابت کاهش مالیات بر ارزش افزوده پس از حذف هزینه تولید محتوا)</small>
                        </div>
                    `;
                }

                // ========== پیام اصلی ==========
                modalMessage.innerHTML = `
                    <div class="text-start">
                        <p class="text-light mb-3">
                            آیا می‌خواهید به جای انتخاب تیم تولید محتوا،
                            <strong class="text-info">محتوای تبلیغ را خودتان آپلود کنید</strong>؟
                        </p>
                        <div class="alert alert-info bg-faded-info text-info text-start">
                            <i class="fi-info-circle me-2"></i>
                            <strong>نکته:</strong>
                            پس از این عملیات، هزینه تولید محتوا از فاکتور حذف شده و
                            <strong class="text-success">مالیات اضافی به کیف پول شما برگشت داده می‌شود</strong>.
                            <br>
                            <span class="text-light-emphasis">اگر پشیمان شدید، کافی است در آن صفحه دکمه <strong class="text-warning">«بازگشت»</strong> را بزنید.</span>
                        </div>
                        ${refundMessage}
                        <p class="text-muted small mb-0">
                            <i class="fi-check-circle me-1 text-success"></i>
                            این گزینه به شما امکان می‌دهد بدون نیاز به تیم تولید محتوا، کمپین خود را تکمیل کنید.
                        </p>
                    </div>
                `;

                // ========== تنظیم دکمه تأیید ==========
                const newBtn = replaceButton(
                    modalBtn,
                    `<i class="fi-check me-1"></i> بله، آپلود می‌کنم`,
                    'btn btn-info rounded-pill px-4'
                );

                newBtn.addEventListener('click', function () {
                    closeModal(modalElement);
                    submitPostForm(`/campaigns/switch-to-ready/${campaignId}/`);
                });

                // ========== نمایش مودال ==========
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
            })
            .catch(error => {
                console.error('❌ خطا در دریافت اطلاعات کمپین:', error);
                showSwitchToReadyModalFallback(campaignId);
            });
    };

    // ==================== Fallback: تبدیل به محتوای آماده ====================

    function showSwitchToReadyModalFallback(campaignId) {
        const { modalElement, modalTitle, modalIcon, modalMessage, modalBtn } = getModalElements();

        if (!modalElement) {
            console.error('❌ globalNotificationModal not found!');
            return;
        }

        modalTitle.innerHTML = `<i class="fi-upload me-2 text-info"></i> آپلود محتوای آماده`;
        modalIcon.className = 'notification-icon info';
        modalIcon.innerHTML = `<i class="fi-info-circle"></i>`;

        modalMessage.innerHTML = `
            <div class="text-start">
                <p class="text-light mb-3">
                    آیا می‌خواهید به جای انتخاب تیم تولید محتوا،
                    <strong class="text-info">محتوای تبلیغ را خودتان آپلود کنید</strong>؟
                </p>
                <div class="alert alert-info bg-faded-info text-info text-start">
                    <i class="fi-info-circle me-2"></i>
                    <strong>نکته:</strong>
                    پس از این عملیات، هزینه تولید محتوا از فاکتور حذف شده و
                    <strong class="text-success">مالیات اضافی به کیف پول شما برگشت داده می‌شود</strong>.
                    <br>
                    <span class="text-light-emphasis">اگر پشیمان شدید، کافی است در آن صفحه دکمه <strong class="text-warning">«بازگشت»</strong> را بزنید.</span>
                </div>
                <p class="text-muted small mb-0">
                    <i class="fi-check-circle me-1 text-success"></i>
                    این گزینه به شما امکان می‌دهد بدون نیاز به تیم تولید محتوا، کمپین خود را تکمیل کنید.
                </p>
            </div>
        `;

        const newBtn = replaceButton(
            modalBtn,
            `<i class="fi-check me-1"></i> بله، آپلود می‌کنم`,
            'btn btn-info rounded-pill px-4'
        );

        newBtn.addEventListener('click', function () {
            closeModal(modalElement);
            submitPostForm(`/campaigns/switch-to-ready/${campaignId}/`);
        });

        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }

    // ==================== حذف کمپین ====================

    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function () {
            const form = document.getElementById('deleteCampaignForm');
            if (form) form.submit();
        });
    }

})();