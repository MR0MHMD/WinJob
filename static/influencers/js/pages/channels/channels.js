// channels.js - نسخه اصلاح شده با پشتیبانی از bio
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
    const bioField = document.querySelector('#channelForm textarea[name="bio"]'); // ✅ اضافه شد

    let currentMode = 'add';
    let currentChannelId = null;

    // ===== تابع به‌روزرسانی شمارش کاراکترهای bio =====
    function updateBioCharCount() {
        const charCount = document.getElementById('bioCharCount');
        if (!bioField || !charCount) return;

        const length = bioField.value.length;
        charCount.textContent = length;

        // تغییر رنگ بر اساس تعداد کاراکترها
        if (length > 720) {
            charCount.style.color = '#dc3545'; // قرمز برای نزدیک به حد مجاز
        } else if (length > 500) {
            charCount.style.color = '#ffc107'; // زرد برای متوسط
        } else {
            charCount.style.color = '#0ce110'; // سبز برای عالی
        }
    }

    // ===== ریست فرم =====
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

        // ریست bio
        if (bioField) {
            bioField.value = '';
            updateBioCharCount(); // به‌روزرسانی شمارش
        }

        currentMode = 'add';
        currentChannelId = null;
        submitBtn.textContent = 'افزودن کانال';
        modalTitle.textContent = 'افزودن کانال جدید';
        form.action = '';
        form.method = 'POST';

        // حذف هر گونه فیلد مخفی extra
        document.querySelectorAll('#channelForm input[name="channel_id"]').forEach(el => {
            if (el.type === 'hidden') el.remove();
        });
    }

    // ===== لود کردن داده‌های کانال در فرم =====
    function loadChannelDataFromButton(btn) {
        const channelId = btn.dataset.id;
        if (!channelId) return;

        // دیباگ
        console.log('Loading channel data for ID:', channelId);

        // ست کردن فیلدها
        if (platformField) platformField.value = btn.dataset.platform || '';
        if (channelIdField) channelIdField.value = btn.dataset.channelIdValue || '';
        if (channelNameField) channelNameField.value = btn.dataset.name || '';

        // فرمت کردن تعداد فالوور با کاما
        if (followersField) {
            const rawFollowers = btn.dataset.followers || '';
            const formattedFollowers = NumberFormatter.formatWithCommas(rawFollowers);
            followersField.value = formattedFollowers;
        }

        if (provinceField) provinceField.value = btn.dataset.province || '';
        if (cityField) cityField.value = btn.dataset.city || '';
        if (categoryField) categoryField.value = btn.dataset.category || '';
        if (urlField) urlField.value = btn.dataset.url || '';

        // ✅ ست کردن bio (مهمترین بخش)
        if (bioField) {
            const bioValue = btn.dataset.bio || '';
            bioField.value = bioValue;
            updateBioCharCount(); // به‌روزرسانی شمارش کاراکترها
            console.log('Bio set to:', bioValue);
        }

        // ست کردن آواتار
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

        // تنظیم حالت ویرایش
        currentMode = 'edit';
        currentChannelId = channelId;
        submitBtn.textContent = 'ذخیره تغییرات';
        modalTitle.textContent = 'ویرایش کانال';
        form.action = `/influencers/my_channels/edit/${channelId}/`;

        // اطمینان از اینکه متد POST هست
        form.method = 'POST';

        // اضافه کردن CSRF token اگر وجود نداره
        if (!form.querySelector('input[name="csrfmiddlewaretoken"]')) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = getCookie('csrftoken');
            form.appendChild(csrfInput);
        }
    }

    // ===== هندلر کلیک ویرایش =====
    function editClickHandler(e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = e.currentTarget;
        loadChannelDataFromButton(btn);
        const modalInstance = bootstrap.Modal.getOrCreateInstance(modal);
        modalInstance.show();
    }

    // ===== بایند دکمه‌های ویرایش =====
    function bindEditButtons() {
        document.querySelectorAll('.edit-channel-btn').forEach(btn => {
            btn.removeEventListener('click', editClickHandler);
            btn.addEventListener('click', editClickHandler);
        });
    }

    // ===== هندلر کلیک حذف =====
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

    // ===== بایند دکمه‌های حذف =====
    function bindDeleteButtons() {
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.removeEventListener('click', deleteClickHandler);
            btn.addEventListener('click', deleteClickHandler);
        });
    }

    // ===== گرفتن Cookie =====
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

    // ===== ری‌بایند همه دکمه‌ها =====
    function rebindAll() {
        bindEditButtons();
        bindDeleteButtons();
    }

    // ===== رویدادهای مودال =====
    modal.addEventListener('hidden.bs.modal', function () {
        resetForm();
    });

    if (addBtn) {
        addBtn.addEventListener('click', function () {
            resetForm();
        });
    }

    // ===== Observer برای تغییرات DOM =====
    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.addedNodes.length) {
                rebindAll();
            }
        });
    });

    const channelsContainer = document.getElementById('channelsContainer');
    if (channelsContainer) {
        observer.observe(channelsContainer, {childList: true, subtree: true});
    }

    // ===== بایند اولیه =====
    rebindAll();
    window.addEventListener('load', rebindAll);

    // ===== رویدادهای bio =====
    document.addEventListener('DOMContentLoaded', function() {
        if (bioField) {
            // رویداد input برای به‌روزرسانی شمارش
            bioField.addEventListener('input', updateBioCharCount);
            // شمارش اولیه
            updateBioCharCount();
        }
    });

    // ===== وقتی مودال نمایش داده میشه، دوباره شمارش رو به‌روز کن =====
    modal.addEventListener('shown.bs.modal', function () {
        updateBioCharCount();
        setupNumberFormatting();
    });

})();

// ===== Utility Functions for Number Formatting =====
const NumberFormatter = {
    cleanNumber: function (value) {
        return value.replace(/,/g, '').replace(/\D/g, '');
    },
    formatWithCommas: function (value) {
        const cleaned = this.cleanNumber(value);
        if (!cleaned) return '';
        return Number(cleaned).toLocaleString('en-US');
    },
    prepareForSubmit: function (value) {
        return this.cleanNumber(value);
    }
};

// ===== ست کردن فرمت‌کننده روی فیلد فالوور =====
function setupNumberFormatting() {
    const followersInput = document.querySelector('#channelForm input[name="followers_count"]');
    if (!followersInput) return;

    followersInput.addEventListener('input', function () {
        const cursorPos = this.selectionStart;
        const formatted = NumberFormatter.formatWithCommas(this.value);
        if (formatted !== this.value) {
            this.value = formatted;
            const newPos = Math.min(cursorPos, formatted.length);
            this.setSelectionRange(newPos, newPos);
        }
    });

    followersInput.addEventListener('blur', function () {
        this.value = NumberFormatter.formatWithCommas(this.value);
    });
}

// ===== قبل از submit، کاماها رو حذف کن =====
function prepareFormForSubmit() {
    const form = document.getElementById('channelForm');
    if (form) {
        form.addEventListener('submit', function () {
            const input = document.querySelector('#channelForm input[name="followers_count"]');
            if (input) {
                input.value = NumberFormatter.prepareForSubmit(input.value);
            }
        });
    }
}

// ===== اجرای توابع =====
document.addEventListener('DOMContentLoaded', function () {
    setupNumberFormatting();
    prepareFormForSubmit();
});

// ===== وقتی مودال بسته میشه =====
const modal = document.getElementById('channelModal');
if (modal) {
    modal.addEventListener('hidden.bs.modal', function () {
        // هیچ کاری لازم نیست چون resetForm قبلاً انجام شده
    });
}