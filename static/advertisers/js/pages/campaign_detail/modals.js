// ==================== توابع نمایش مودال‌ها ====================

(function () {
    'use strict';

    // ==================== تابع نمایش مودال ادامه بدون جایگزینی ====================
    window.showContinueWithoutReplacementModal = function (campaignId) {
        const modalElement = document.getElementById('globalNotificationModal');
        const modalTitle = document.getElementById('notificationModalTitle');
        const modalIcon = document.getElementById('notificationModalIcon');
        const modalMessage = document.getElementById('notificationModalMessage');
        const modalBtn = document.getElementById('notificationModalBtn');

        // ========== دریافت اطلاعات کمپین از طریق AJAX ==========
        fetch(`/campaigns/api/campaign-tax-info/${campaignId}/`)
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    showContinueWithoutReplacementModalFallback(campaignId);
                    return;
                }

                const influencerCost = data.influencer_cost || 0;
                const contentCost = data.content_cost || 0;
                const commission = data.commission || 0;
                const oldVat = data.total_vat || 0;
                const oldPayable = data.payable_amount || 0;

                // ========== محاسبه هزینه ناشران جدید (بدون ناشران رد شده) ==========
                // از API هزینه ناشران جدید رو دریافت می‌کنیم
                const newInfluencerCost = data.new_influencer_cost || influencerCost;

                // ========== محاسبه مالیات جدید (با هزینه ناشران جدید) ==========
                // مالیات جدید = (هزینه ناشران جدید + هزینه محتوا + کمیسیون) × ۱۰٪
                const taxBase = newInfluencerCost + contentCost + commission;
                const newVat = Math.round(taxBase * 0.10);

                // ========== ما به التفاوت مالیات ==========
                const vatDiff = newVat - oldVat;  // این عدد منفی خواهد بود
                const refundAmount = Math.abs(vatDiff);  // مبلغ برگشتی به کاربر

                // ========== تنظیم عنوان ==========
                modalTitle.innerHTML = `<i class="fi-alert-triange me-2 text-warning"></i> ادامه بدون جایگزینی`;

                // ========== تنظیم آیکون ==========
                modalIcon.className = 'notification-icon warning';
                modalIcon.innerHTML = `<i class="fi-alert-triange"></i>`;

                // ========== تنظیم متن پیام با نمایش مبلغ برگشتی ==========
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

                // ========== تنظیم دکمه‌ها ==========
                modalBtn.innerHTML = `<i class="fi-check me-1"></i> بله، ادامه می‌دم`;
                modalBtn.className = 'btn btn-success rounded-pill px-4';

                const newBtn = modalBtn.cloneNode(true);
                modalBtn.parentNode.replaceChild(newBtn, modalBtn);

                newBtn.addEventListener('click', function () {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();

                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = `/campaigns/continue-without-replacement/${campaignId}/`;

                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrfmiddlewaretoken';
                    csrfInput.value = getCookie('csrftoken');
                    form.appendChild(csrfInput);

                    document.body.appendChild(form);
                    form.submit();
                });

                const cancelBtn = document.querySelector('#globalNotificationModal .btn-close');
                const newCancelBtn = cancelBtn.cloneNode(true);
                cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

                newCancelBtn.addEventListener('click', function () {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();
                });

                const modal = new bootstrap.Modal(modalElement);
                modal.show();

                modalElement.addEventListener('hidden.bs.modal', function () {
                }, {once: true});
            })
            .catch(error => {
                console.error('❌ خطا در دریافت اطلاعات کمپین:', error);
                showContinueWithoutReplacementModalFallback(campaignId);
            });
    };

    // ==================== تابع نمایش مودال تبدیل به محتوای آماده ====================
    window.showSwitchToReadyModal = function (campaignId) {
        const modalElement = document.getElementById('globalNotificationModal');
        const modalTitle = document.getElementById('notificationModalTitle');
        const modalIcon = document.getElementById('notificationModalIcon');
        const modalMessage = document.getElementById('notificationModalMessage');
        const modalBtn = document.getElementById('notificationModalBtn');

        // ========== دریافت اطلاعات کمپین از طریق AJAX ==========
        fetch(`/campaigns/api/campaign-tax-info/${campaignId}/`)
            .then(response => response.json())
            .then(data => {
                const contentCost = data.content_cost || 0;
                const contentVat = data.content_vat || 0;
                const influencerCost = data.influencer_cost || 0;
                const commission = data.commission || 0;
                const oldVat = data.total_vat || 0;

                // ========== محاسبه مالیات جدید (بدون هزینه محتوا) ==========
                // مالیات جدید = (هزینه ناشران + کمیسیون) × ۱۰٪
                const newVat = Math.round((influencerCost + commission) * 0.10);

                // ========== ما به التفاوت مالیات (منفی = برگشت به کاربر) ==========
                const vatDiff = newVat - oldVat;  // این عدد منفی خواهد بود
                const refundAmount = Math.abs(vatDiff);  // مبلغ برگشتی به کاربر

                // ========== تنظیم عنوان ==========
                modalTitle.innerHTML = `<i class="fi-upload me-2 text-info"></i> آپلود محتوای آماده`;

                // ========== تنظیم آیکون ==========
                modalIcon.className = 'notification-icon info';
                modalIcon.innerHTML = `<i class="fi-info-circle"></i>`;

                // ========== تنظیم متن پیام با نمایش مبلغ برگشتی ==========
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

                // ========== تنظیم دکمه‌ها ==========
                modalBtn.innerHTML = `<i class="fi-check me-1"></i> بله، آپلود می‌کنم`;
                modalBtn.className = 'btn btn-info rounded-pill px-4';

                const newBtn = modalBtn.cloneNode(true);
                modalBtn.parentNode.replaceChild(newBtn, modalBtn);

                newBtn.addEventListener('click', function () {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();

                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = `/campaigns/switch-to-ready/${campaignId}/`;

                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrfmiddlewaretoken';
                    csrfInput.value = getCookie('csrftoken');
                    form.appendChild(csrfInput);

                    document.body.appendChild(form);
                    form.submit();
                });

                const cancelBtn = document.querySelector('#globalNotificationModal .btn-close');
                const newCancelBtn = cancelBtn.cloneNode(true);
                cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

                newCancelBtn.addEventListener('click', function () {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();
                });

                const modal = new bootstrap.Modal(modalElement);
                modal.show();

                modalElement.addEventListener('hidden.bs.modal', function () {
                }, {once: true});
            })
            .catch(error => {
                console.error('❌ خطا در دریافت اطلاعات کمپین:', error);
                // در صورت خطا، مودال رو بدون اطلاعات مالی نشون بده
                showSwitchToReadyModalFallback(campaignId);
            });
    };

    // ==================== حذف کمپین ====================
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', function () {
        document.getElementById('deleteCampaignForm').submit();
    });

})();