// notification_list.js

document.addEventListener('DOMContentLoaded', function () {
    // دریافت توکن CSRF از متای صفحه (که باید در parent/base.html حتماً تعریف شده باشد)
    function getCSRFToken() {
        const cookieValue = document.cookie.match('(^|; )csrftoken=([^;]*)');
        return cookieValue ? cookieValue[2] : '';
    }

    // ۱. خواندن همه
    const markAllReadBtn = document.getElementById('markAllReadBtn');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function () {
            fetch(markAllReadBtn.dataset.markAllUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json'
                },
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.querySelectorAll('.notif-unread').forEach(card => {
                            card.classList.remove('notif-unread');
                        });
                        markAllReadBtn.style.display = 'none';
                        const badge = document.getElementById('unreadBadge');
                        if (badge) badge.style.display = 'none';
                        if (typeof showNotificationModal === 'function') {
                            showNotificationModal('موفقیت', 'تمامی اعلان‌ها خوانده شدند.', 'success');
                        }
                    }
                });
        });
    }

    // ۲. ذخیره تنظیمات مودال
    const saveBtn = document.getElementById('savePreferencesBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            const form = document.getElementById('preferencesForm');
            const data = {};
            form.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                data[checkbox.name] = checkbox.checked;
            });

            fetch(saveBtn.dataset.savePreferencesUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
                        modal.hide();
                        if (typeof showNotificationModal === 'function') {
                            showNotificationModal('موفقیت', 'تنظیمات شما با موفقیت بروزرسانی شد.', 'success');
                        }
                    }
                });
        });
    }

    // ۳. مارک کردن یک نوتیفیکیشن هنگام کلیک روی مشاهده جزئیات
    document.querySelectorAll('.mark-notification-read').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const markUrl = this.dataset.markUrl;
            const targetUrl = this.dataset.notifLink;

            fetch(markUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json'
                }
            })
                .then(response => response.json())
                .then(data => {
                    window.location.href = targetUrl;
                })
                .catch(() => {
                    window.location.href = targetUrl;
                });
        });
    });
});