// ==================== توابع کمکی عمومی ====================

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

function showMessage(title, message, type = 'info', onClose = null) {
    if (typeof window.showNotificationModal === 'function') {
        window.showNotificationModal(title, message, type, onClose);
    } else {
        alert(message);
        if (onClose) onClose();
    }
}

function showConfirmModal(title, message, onConfirm, onCancel = null) {
    let confirmModal = document.getElementById('customConfirmModal');
    if (!confirmModal) {
        confirmModal = document.createElement('div');
        confirmModal.id = 'customConfirmModal';
        confirmModal.className = 'modal fade';
        confirmModal.setAttribute('tabindex', '-1');
        confirmModal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content bg-dark border-light">
                    <div class="modal-header border-light">
                        <h5 class="modal-title text-light">
                            <i class="bi bi-exclamation-triangle-fill me-2 text-warning"></i>
                            <span id="confirmModalTitle">تأیید عملیات</span>
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <div class="notification-icon warning mb-3">
                            <i class="bi bi-exclamation-triangle-fill fs-1"></i>
                        </div>
                        <p class="text-light mb-0" id="confirmModalMessage">آیا از انجام این عملیات مطمئن هستید؟</p>
                    </div>
                    <div class="modal-footer border-light">
                        <button type="button" class="btn btn-secondary rounded-pill px-4" id="confirmModalCancelBtn">
                            <i class="bi bi-x-lg me-1"></i> انصراف
                        </button>
                        <button type="button" class="btn btn-primary rounded-pill px-4" id="confirmModalConfirmBtn">
                            <i class="bi bi-check-lg me-1"></i> تأیید
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(confirmModal);
    }
    document.getElementById('confirmModalTitle').innerHTML = ` ${title}`;
    document.getElementById('confirmModalMessage').innerHTML = message;
    const modal = new bootstrap.Modal(confirmModal);
    modal.show();
    const confirmBtn = document.getElementById('confirmModalConfirmBtn');
    const cancelBtn = document.getElementById('confirmModalCancelBtn');
    const cleanup = () => {
        confirmBtn.removeEventListener('click', handleConfirm);
        cancelBtn.removeEventListener('click', handleCancel);
        confirmModal.addEventListener('hidden.bs.modal', () => modal.dispose(), { once: true });
    };
    const handleConfirm = () => {
        modal.hide();
        cleanup();
        if (onConfirm) onConfirm();
    };
    const handleCancel = () => {
        modal.hide();
        cleanup();
        if (onCancel) onCancel();
    };
    confirmBtn.addEventListener('click', handleConfirm);
    cancelBtn.addEventListener('click', handleCancel);
}

// نمایش پیام بدون داده در نمودار
function showNoDataMessage(canvas, message) {
    const parent = canvas.parentElement;
    canvas.style.display = 'none';
    let msgDiv = parent.querySelector('.no-data-message');
    if (!msgDiv) {
        msgDiv = document.createElement('div');
        msgDiv.className = 'no-data-message text-center py-5';
        msgDiv.innerHTML = `<i class="fi-inbox fs-1 text-muted opacity-50 mb-2 d-block"></i><p class="text-muted mb-0">${message}</p>`;
        parent.appendChild(msgDiv);
    } else {
        msgDiv.style.display = 'block';
    }
}

// ==================== مدیریت فایل مرجع ویرایش ====================
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
        selectedFileDiv.querySelector('.remove-revision-file-btn')?.addEventListener('click', function() {
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
    revisionFileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            selectedRevisionFile = this.files[0];
            updateRevisionFileDisplay();
        }
    });
}

// ==================== ثبت درخواست ویرایش ====================
const revisionForm = document.getElementById('revisionForm');
if (revisionForm) {
    revisionForm.addEventListener('submit', async function(e) {
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
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
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
    btn.addEventListener('click', async function() {
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

// ==================== نمودار کلیک‌های روزانه (کار با هر دو حالت عادی و رایگان) ====================
const clicksCanvas = document.getElementById('dailyClicksChart');
if (clicksCanvas) {
    const hasData = clicksCanvas.dataset.hasdata === 'true';
    let labels = [];
    let datasets = [];

    if (hasData) {
        try {
            labels = JSON.parse(clicksCanvas.dataset.labels || '[]');
            datasets = JSON.parse(clicksCanvas.dataset.datasets || '[]');
        } catch(e) {
            console.error('خطا در پارس داده‌های نمودار کلیک:', e);
        }
    }

    if (labels.length > 0 && datasets.length > 0) {
        const hasNonZero = datasets.some(ds => ds.data.some(v => v > 0));
        if (hasNonZero) {
            // استایل پیشرفته دیتاست‌ها (چه یک دیتاست برای رایگان، چه چندتا برای عادی)
            const enhancedDatasets = datasets.map(ds => ({
                ...ds,
                borderWidth: 2,
                backgroundColor: ds.borderColor ? (ds.borderColor + '1A') : 'rgba(253, 86, 49, 0.1)',
                pointBackgroundColor: ds.borderColor || '#fd5631',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.3,
                fill: true
            }));

            new Chart(clicksCanvas.getContext('2d'), {
                type: 'line',
                data: { labels, datasets: enhancedDatasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#fff',
                                font: { size: 12, family: 'IRANSans, Vazir' },
                                boxWidth: 12,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(19,16,36,0.8)',
                            titleColor: '#fff',
                            bodyColor: '#9691a4',
                            borderColor: '#fd5631',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y.toLocaleString() + ' کلیک';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#9691a4',
                                stepSize: 1,
                                precision: 0,
                                font: { size: 11 }
                            },
                            title: {
                                display: true,
                                text: 'تعداد کلیک‌ها',
                                color: '#9691a4',
                                font: { size: 11 }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#9691a4',
                                maxRotation: 45,
                                minRotation: 45,
                                font: { size: 10 }
                            }
                        }
                    },
                    interaction: { mode: 'index', intersect: false }
                }
            });
        } else {
            showNoDataMessage(clicksCanvas, 'هیچ کلیکی در ۳۰ روز اخیر ثبت نشده است');
        }
    } else {
        showNoDataMessage(clicksCanvas, 'هیچ داده‌ای برای نمایش وجود ندارد');
    }
}