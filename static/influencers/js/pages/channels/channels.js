// channels.js - نسخه اصلاح شده
(function () {
    'use strict';

    const modal = document.getElementById('channelModal');
    const modalTitle = document.getElementById('channelModalLabel');
    const form = document.getElementById('channelForm');
    const submitBtn = document.getElementById('modalSubmitBtn');
    const addBtn = document.getElementById('addChannelBtn');

    const platformField = document.querySelector('#channelForm select[name="platform"]');
    const channelIdField = document.querySelector('#channelForm input[name="channel_id"]');
    const channelNameField = document.querySelector('#channelForm input[name="channel_name"]');
    const followersField = document.querySelector('#channelForm input[name="followers_count"]');
    const provinceField = document.querySelector('#channelForm select[name="province"]');
    const cityField = document.querySelector('#channelForm select[name="city"]');
    const categoryField = document.querySelector('#channelForm select[name="category"]');
    const urlField = document.querySelector('#channelForm input[name="url"]');
    const avatarInput = document.querySelector('#channelForm input[type="file"][name="avatar"]');

    let currentMode = 'add';
    let currentChannelId = null;

    function resetForm() {
        form.reset();
        const previewImg = document.getElementById('avatar-preview-img');
        const placeholder = document.getElementById('avatar-placeholder');
        const removeBtn = document.getElementById('avatar-remove-btn');
        const fileNameSpan = document.getElementById('avatar-file-name');
        const wrapper = document.getElementById('avatar-upload-wrapper');
        if (previewImg) {
            previewImg.src = '';
            previewImg.style.display = 'none';
        }
        if (placeholder) placeholder.style.display = 'flex';
        if (removeBtn) removeBtn.style.display = 'none';
        if (wrapper) wrapper.classList.remove('has-image');
        if (fileNameSpan) fileNameSpan.textContent = '';
        if (avatarInput) avatarInput.value = '';
        currentMode = 'add';
        currentChannelId = null;
        submitBtn.textContent = 'افزودن کانال';
        modalTitle.textContent = 'افزودن کانال جدید';
        form.action = '';
    }

    function loadChannelDataFromButton(btn) {
        const channelId = btn.dataset.id;
        if (!channelId) return;

        // دیباگ - چاپ مقادیر دریافتی
        console.log('Channel ID:', channelId);
        console.log('Channel Name:', btn.dataset.name);
        console.log('Followers:', btn.dataset.followers);
        console.log('Followers Field:', followersField);

        if (platformField) platformField.value = btn.dataset.platform || '';
        if (channelIdField) channelIdField.value = btn.dataset.channelIdValue || '';
        if (channelNameField) channelNameField.value = btn.dataset.name || '';

        // این قسمت مهمه - مقدار رو با کاما فرمت کن
        if (followersField) {
            const rawFollowers = btn.dataset.followers || '';
            // فرمت کردن عدد با کاما
            const formattedFollowers = NumberFormatter.formatWithCommas(rawFollowers);
            followersField.value = formattedFollowers;
            console.log('Raw followers:', rawFollowers);
            console.log('Formatted followers:', formattedFollowers);
            console.log('Followers field value after set:', followersField.value);
        }

        if (provinceField) provinceField.value = btn.dataset.province || '';
        if (cityField) cityField.value = btn.dataset.city || '';
        if (categoryField) categoryField.value = btn.dataset.category || '';
        if (urlField) urlField.value = btn.dataset.url || '';

        const avatarUrl = btn.dataset.avatarUrl;
        const previewImg = document.getElementById('avatar-preview-img');
        const placeholder = document.getElementById('avatar-placeholder');
        const removeBtn = document.getElementById('avatar-remove-btn');
        const fileNameSpan = document.getElementById('avatar-file-name');
        const wrapper = document.getElementById('avatar-upload-wrapper');
        if (avatarUrl && previewImg) {
            previewImg.src = avatarUrl;
            previewImg.style.display = 'block';
            placeholder.style.display = 'none';
            removeBtn.style.display = 'flex';
            wrapper.classList.add('has-image');
            if (fileNameSpan) fileNameSpan.textContent = 'تصویر فعلی';
        } else {
            if (previewImg) previewImg.style.display = 'none';
            if (placeholder) placeholder.style.display = 'flex';
            if (removeBtn) removeBtn.style.display = 'none';
            if (wrapper) wrapper.classList.remove('has-image');
            if (fileNameSpan) fileNameSpan.textContent = '';
        }
        if (avatarInput) avatarInput.value = '';

        currentMode = 'edit';
        currentChannelId = channelId;
        submitBtn.textContent = 'ذخیره تغییرات';
        modalTitle.textContent = 'ویرایش کانال';
        form.action = `/influencers/my_channels/edit/${channelId}/`;
    }

    function editClickHandler(e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = e.currentTarget;
        loadChannelDataFromButton(btn);
        const modalInstance = bootstrap.Modal.getOrCreateInstance(modal);
        modalInstance.show();
    }

    function bindEditButtons() {
        document.querySelectorAll('.edit-channel-btn').forEach(btn => {
            btn.removeEventListener('click', editClickHandler);
            btn.addEventListener('click', editClickHandler);
        });
    }

    function bindDeleteButtons() {
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.removeEventListener('click', deleteClickHandler);
            btn.addEventListener('click', deleteClickHandler);
        });
    }

    function deleteClickHandler(e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = e.currentTarget;
        const channelId = btn.dataset.id;
        const channelName = btn.dataset.name;
        if (!channelId) return;

        const overlay = document.getElementById('confirm-overlay');
        const confirmChannelName = document.getElementById('confirm-channel-name');
        const confirmDeleteBtn = document.getElementById('confirm-delete');
        const cancelBtn = document.getElementById('confirm-cancel');

        confirmChannelName.innerText = channelName;
        overlay.classList.add('active');

        function onConfirm() {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/influencers/my_channels/delete/${channelId}/`;
            const csrf = document.createElement('input');
            csrf.type = 'hidden';
            csrf.name = 'csrfmiddlewaretoken';
            csrf.value = getCookie('csrftoken');
            form.appendChild(csrf);
            document.body.appendChild(form);
            form.submit();
        }

        function onCancel() {
            overlay.classList.remove('active');
            confirmDeleteBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
        }

        confirmDeleteBtn.removeEventListener('click', onConfirm);
        cancelBtn.removeEventListener('click', onCancel);
        confirmDeleteBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);
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

    modal.addEventListener('hidden.bs.modal', function () {
        resetForm();
    });

    if (addBtn) {
        addBtn.addEventListener('click', function () {
            resetForm();
        });
    }

    // ری‌بایند کردن دکمه‌ها بعد از هر تغییر در DOM (مثلاً بعد از AJAX)
    function rebindAll() {
        bindEditButtons();
        bindDeleteButtons();
    }

    // Observer برای تغییرات DOM (مثلاً وقتی کانال جدید اضافه میشه)
    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.addedNodes.length) {
                rebindAll();
            }
        });
    });

    // شروع observer روی container کانال‌ها
    const channelsContainer = document.getElementById('channelsContainer');
    if (channelsContainer) {
        observer.observe(channelsContainer, {childList: true, subtree: true});
    }

    // بایند اولیه
    rebindAll();

    // همچنین بعد از لود کامل صفحه دوباره بایند کن
    window.addEventListener('load', rebindAll);
})();

// ===== Utility Functions for Number Formatting =====
const NumberFormatter = {
    // حذف همه کاراکترهای غیرعددی
    cleanNumber: function (value) {
        return value.replace(/,/g, '').replace(/\D/g, '');
    },

    // فرمت با کاما
    formatWithCommas: function (value) {
        const cleaned = this.cleanNumber(value);
        if (!cleaned) return '';
        return Number(cleaned).toLocaleString('en-US');
    },

    // آماده‌سازی برای ارسال به سرور (حذف کاما)
    prepareForSubmit: function (value) {
        return this.cleanNumber(value);
    }
};

// ست کردن فرمت‌کننده روی فیلد
function setupNumberFormatting() {
    const followersInput = document.querySelector('#channelForm input[name="followers_count"]');
    if (!followersInput) return;

    // وقتی کاربر تایپ میکنه
    followersInput.addEventListener('input', function () {
        const cursorPos = this.selectionStart;
        const formatted = NumberFormatter.formatWithCommas(this.value);

        if (formatted !== this.value) {
            this.value = formatted;
            // موقعیتカーソル رو حفظ کن
            const newPos = Math.min(cursorPos, formatted.length);
            this.setSelectionRange(newPos, newPos);
        }
    });

    // وقتی فیلد رو ترک میکنه
    followersInput.addEventListener('blur', function () {
        this.value = NumberFormatter.formatWithCommas(this.value);
    });
}

// قبل از submit، کاماها رو حذف کن
function prepareFormForSubmit() {
    const form = document.getElementById('channelForm');
    form.addEventListener('submit', function () {
        const input = document.querySelector('#channelForm input[name="followers_count"]');
        if (input) {
            input.value = NumberFormatter.prepareForSubmit(input.value);
        }
    });
}

// اجرای توابع
document.addEventListener('DOMContentLoaded', function () {
    setupNumberFormatting();
    prepareFormForSubmit();
});

// وقتی مودال باز میشه دوباره اجرا کن
modal.addEventListener('shown.bs.modal', function () {
    setupNumberFormatting();
});