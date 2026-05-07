(function() {
    'use strict';

    const wrapper = document.getElementById('avatar-upload-wrapper');
    const fileInput = document.querySelector('#avatar-upload-wrapper input[type="file"]');
    const placeholder = document.getElementById('avatar-placeholder');
    const previewImg = document.getElementById('avatar-preview-img');
    const removeBtn = document.getElementById('avatar-remove-btn');
    const fileNameSpan = document.getElementById('avatar-file-name');

    if (!wrapper || !fileInput) return;

    // کلیک روی کادر => باز کردن فایل منیجر
    wrapper.addEventListener('click', (e) => {
        if (e.target !== removeBtn && !removeBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    // drag & drop
    wrapper.addEventListener('dragover', (e) => {
        e.preventDefault();
        wrapper.classList.add('drag-over');
    });
    wrapper.addEventListener('dragleave', () => {
        wrapper.classList.remove('drag-over');
    });
    wrapper.addEventListener('drop', (e) => {
        e.preventDefault();
        wrapper.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length) {
            fileInput.files = files;       // به input مخفی تزریق می‌کنیم
            updatePreview(files[0]);       // پیش‌نمایش را آپدیت کن
        }
    });

    // وقتی فایل از طریق کلیک انتخاب شد
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            updatePreview(file);
        } else {
            clearPreview();   // اگر کاربر در کادر انتخاب فایل cancel کرد
        }
    });

    // دکمه حذف
    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearPreview();
        fileInput.value = '';            // پاک کردن input
    });

    function updatePreview(file) {
        // نمایش نام فایل
        if (fileNameSpan) {
            fileNameSpan.textContent = file.name;
        }

        // اگر فایل تصویر هست، پیش‌نمایش را نشان بده
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
                placeholder.style.display = 'none';
                removeBtn.style.display = 'flex';    // دکمه حذف ظاهر شود
                wrapper.classList.add('has-image');
            };
            reader.readAsDataURL(file);
        } else {
            // اگر فایل عکس نبود، فقط placeholder پنهان و اسم فایل رو نشون بده (بدون پیش‌نمایش)
            placeholder.style.display = 'none';
            removeBtn.style.display = 'flex';
            wrapper.classList.add('has-image');
            if (fileNameSpan) fileNameSpan.textContent = file.name;
        }
    }

    function clearPreview() {
        previewImg.src = '';
        previewImg.style.display = 'none';
        placeholder.style.display = 'flex';
        removeBtn.style.display = 'none';
        wrapper.classList.remove('has-image');
        if (fileNameSpan) fileNameSpan.textContent = '';
    }

})();