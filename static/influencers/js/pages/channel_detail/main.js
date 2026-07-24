// ==================== توابع عمومی ====================

function copyToClipboard(elementId) {
    const text = document.getElementById(elementId).innerText;
    navigator.clipboard.writeText(text);
    const btn = document.getElementById('copyCodeBtn');
    if (btn) {
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="fi-check"></i> کپی شد!';
        setTimeout(() => btn.innerHTML = original, 1500);
    }
}

function contactSupport() {
    if (typeof showNotificationModal !== 'undefined') {
        showNotificationModal('پشتیبانی', 'لطفاً از طریق صفحه "تماس با ما" با پشتیبانی در ارتباط باشید.', 'info');
    }
}

function reportUser() {
    if (typeof showNotificationModal !== 'undefined') {
        showNotificationModal('گزارش تخلف', 'گزارش شما با موفقیت ثبت شد. تیم ما ظرف 24 ساعت بررسی خواهد کرد.', 'warning');
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function (m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    }).replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, function (c) {
        return c;
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}