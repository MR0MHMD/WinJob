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
        confirmModal.addEventListener('hidden.bs.modal', () => modal.dispose(), {once: true});
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