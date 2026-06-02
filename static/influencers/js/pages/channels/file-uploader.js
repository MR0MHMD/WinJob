// file-uploader.js (بدون تغییر، همان کد قبلی)
(function() {
    'use strict';

    const wrapper = document.getElementById('avatar-upload-wrapper');
    const fileInput = document.querySelector('#avatar-upload-wrapper input[type="file"]');
    const placeholder = document.getElementById('avatar-placeholder');
    const previewImg = document.getElementById('avatar-preview-img');
    const removeBtn = document.getElementById('avatar-remove-btn');
    const fileNameSpan = document.getElementById('avatar-file-name');

    if (!wrapper || !fileInput) return;

    wrapper.addEventListener('click', (e) => {
        if (e.target !== removeBtn && !removeBtn.contains(e.target)) {
            fileInput.click();
        }
    });

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
            fileInput.files = files;
            updatePreview(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            updatePreview(file);
        } else {
            clearPreview();
        }
    });

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearPreview();
        fileInput.value = '';
    });

    function updatePreview(file) {
        if (fileNameSpan) {
            fileNameSpan.textContent = file.name;
        }
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
                placeholder.style.display = 'none';
                removeBtn.style.display = 'flex';
                wrapper.classList.add('has-image');
            };
            reader.readAsDataURL(file);
        } else {
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