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
                </div>
                <p class="text-muted small mb-0">
                    <i class="fi-clock me-1"></i>
                    در صورت انتخاب این گزینه، کمپین شما به حالت تایید شده بازمی‌گردد.
                </p>
            </div>
        `;

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
    };

    // ==================== تابع نمایش مودال تبدیل به محتوای آماده (اصلاح‌شده) ====================
    window.showSwitchToReadyModal = function (campaignId) {
        const modalElement = document.getElementById('globalNotificationModal');
        const modalTitle = document.getElementById('notificationModalTitle');
        const modalIcon = document.getElementById('notificationModalIcon');
        const modalMessage = document.getElementById('notificationModalMessage');
        const modalBtn = document.getElementById('notificationModalBtn');

        // ========== تنظیم عنوان ساده ==========
        modalTitle.innerHTML = `<i class="fi-upload me-2 text-info"></i> آپلود محتوای آماده`;

        // ========== تنظیم آیکون ==========
        modalIcon.className = 'notification-icon info';
        modalIcon.innerHTML = `<i class="fi-info-circle"></i>`;

        // ========== تنظیم متن پیام (ساده و بدون هشدارهای ترسناک) ==========
        modalMessage.innerHTML = `
            <div class="text-start">
                <p class="text-light mb-3">
                    آیا می‌خواهید به جای انتخاب تیم تولید محتوا، 
                    <strong class="text-info">محتوای تبلیغ را خودتان آپلود کنید</strong>؟
                </p>
                <div class="alert alert-info bg-faded-info text-info text-start">
                    <i class="fi-info-circle me-2"></i>
                    <strong>نکته:</strong>
                    پس از این عملیات، به صفحه آپلود محتوا هدایت می‌شوید.
                    <br>
                    <span class="text-light-emphasis">اگر پشیمان شدید، کافی است در آن صفحه دکمه <strong class="text-warning">«بازگشت»</strong> را بزنید.</span>
                </div>
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
    };

    // ==================== حذف کمپین ====================
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', function () {
        document.getElementById('deleteCampaignForm').submit();
    });

})();