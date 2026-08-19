// ==================== مدیریت فایل مرجع ویرایش ====================

(function () {
    'use strict';

    let selectedRevisionFile = null;
    const revisionDropzone = document.getElementById('revisionDropzone');
    const revisionFileInput = document.getElementById('revisionFileInput');
    const selectedFileContainer = document.getElementById('selectedFileContainer');
    const selectedFileDiv = document.getElementById('selectedFile');
    const dropzoneText = document.getElementById('dropzoneText');

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function getFileIcon(fileName) {
        const ext = fileName.split('.').pop().toLowerCase();
        const icons = {
            'jpg': 'fi-image', 'jpeg': 'fi-image', 'webp': 'fi-image', 'gif': 'fi-image',
            'mp4': 'fi-video', 'avi': 'fi-video', 'mov': 'fi-video',
            'mp3': 'fi-music', 'wav': 'fi-music',
            'pdf': 'fi-file', 'doc': 'fi-file', 'docx': 'fi-file',
            'zip': 'fi-archive', 'rar': 'fi-archive'
        };
        return icons[ext] || 'fi-file';
    }

    function updateRevisionFileDisplay() {
        if (!selectedRevisionFile) {
            if (selectedFileContainer) selectedFileContainer.style.display = 'none';
            if (dropzoneText) dropzoneText.innerHTML = 'برای آپلود کلیک کنید یا فایل را بکشید';
            return;
        }
        if (selectedFileContainer) selectedFileContainer.style.display = 'block';
        if (dropzoneText) dropzoneText.innerHTML = '1 فایل انتخاب شده';
        if (selectedFileDiv) {
            selectedFileDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center p-3 rounded-2 bg-faded-dark">
                    <div class="d-flex align-items-center gap-3 flex-grow-1">
                        <div class="file-icon-small"><i class="${getFileIcon(selectedRevisionFile.name)}"></i></div>
                        <div class="flex-grow-1">
                            <div class="small text-light fw-semibold">${selectedRevisionFile.name.length > 35 ? selectedRevisionFile.name.substring(0, 35) + '...' : selectedRevisionFile.name}</div>
                            <div class="small text-muted">${formatFileSize(selectedRevisionFile.size)}</div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-sm btn-link text-danger p-0 remove-revision-file-btn"><i class="fi-x"></i></button>
                </div>
            `;
            selectedFileDiv.querySelector('.remove-revision-file-btn')?.addEventListener('click', function () {
                selectedRevisionFile = null;
                if (revisionFileInput) revisionFileInput.value = '';
                updateRevisionFileDisplay();
            });
        }
    }

    if (revisionDropzone) {
        revisionDropzone.addEventListener('click', () => revisionFileInput?.click());
        revisionDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            revisionDropzone.style.borderColor = '#fd5631';
            revisionDropzone.style.background = 'rgba(253, 86, 49, 0.05)';
        });
        revisionDropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            revisionDropzone.style.borderColor = 'rgba(255, 255, 255, 0.1)';
            revisionDropzone.style.background = 'transparent';
        });
        revisionDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            revisionDropzone.style.borderColor = 'rgba(255, 255, 255, 0.1)';
            revisionDropzone.style.background = 'transparent';
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                selectedRevisionFile = files[0];
                updateRevisionFileDisplay();
            }
        });
    }
    if (revisionFileInput) {
        revisionFileInput.addEventListener('change', function () {
            if (this.files.length > 0) {
                selectedRevisionFile = this.files[0];
                updateRevisionFileDisplay();
            }
        });
    }

    // ==================== ثبت درخواست ویرایش ====================
    const revisionForm = document.getElementById('revisionForm');
    if (revisionForm) {
        revisionForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const feedback = document.querySelector('textarea[name="feedback"]').value;
            if (!feedback.trim()) {
                showMessage('خطا', 'لطفاً توضیحات ویرایش را وارد کنید', 'error');
                return;
            }
            const orderId = document.querySelector('.request-revision-btn')?.dataset.orderId;
            if (!orderId) return;
            const formData = new FormData();
            formData.append('feedback', feedback.trim());
            if (selectedRevisionFile) formData.append('revision_file', selectedRevisionFile);
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fi-loading"></i> در حال ارسال...';
            submitBtn.disabled = true;
            try {
                const response = await fetch(`/advertisers/campaign/order/${orderId}/request-revision/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken')},
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('revisionModal'));
                    if (modal) modal.hide();
                    showMessage('موفقیت', data.message, 'success', () => location.reload());
                } else {
                    showMessage('خطا', data.error, 'error');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            } catch (error) {
                console.error(error);
                showMessage('خطا', 'خطا در ارتباط با سرور', 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // ==================== تأیید نهایی سفارش ====================
    document.querySelectorAll('.final-accept-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const orderId = this.dataset.orderId;
            showConfirmModal(
                'تأیید نهایی سفارش',
                'آیا از تأیید نهایی این سفارش مطمئن هستید؟\nپس از تأیید، این فایل به عنوان فایل اصلی کمپین شما در نظر گرفته خواهد شد.',
                async () => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fi-loading"></i> در حال پردازش...';
                    this.disabled = true;
                    try {
                        const response = await fetch(`/advertisers/campaign/order/${orderId}/final-accept/`, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': getCookie('csrftoken'),
                                'Content-Type': 'application/x-www-form-urlencoded',
                            }
                        });
                        const data = await response.json();
                        if (data.success) {
                            showMessage('موفقیت', data.message, 'success', () => location.reload());
                        } else {
                            showMessage('خطا', data.error, 'error');
                            this.innerHTML = originalText;
                            this.disabled = false;
                        }
                    } catch (error) {
                        showMessage('خطا', 'خطا در ارتباط با سرور', 'error');
                        this.innerHTML = originalText;
                        this.disabled = false;
                    }
                }
            );
        });
    });

})();