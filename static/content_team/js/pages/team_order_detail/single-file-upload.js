// =============================================
// 3. single-file-upload.js - مدیریت آپلود فایل‌های SINGLE
// =============================================

(function () {
    const dropzoneArea = document.getElementById('dropzoneArea');
    const fileInput = document.getElementById('fileInput');
    const selectedFileContainer = document.getElementById('selectedFileContainer');
    const selectedFileDiv = document.getElementById('selectedFile');
    const dropzoneText = document.getElementById('dropzoneText');
    const fileTypeAlert = document.getElementById('fileTypeAlert');
    const fileTypeAlertText = document.getElementById('fileTypeAlertText');
    const modalBody = document.getElementById('deliveryModalBody');
    const serviceName = modalBody ? modalBody.dataset.serviceName : '';

    // نمایش هشدار نوع فایل
    if (fileTypeAlert && serviceName) {
        const allowed = getServiceFileTypes(serviceName);
        fileTypeAlertText.textContent = allowed.message;
        fileTypeAlert.style.display = 'block';
    }

    window.selectedDeliveryFile = null;

    function updateSingleFileDisplay() {
        if (!window.selectedDeliveryFile) {
            if (selectedFileContainer) selectedFileContainer.style.display = 'none';
            if (dropzoneText) dropzoneText.innerHTML = 'برای آپلود کلیک کنید یا فایل را بکشید';
            return;
        }

        if (selectedFileContainer) selectedFileContainer.style.display = 'block';
        if (dropzoneText) dropzoneText.innerHTML = '1 فایل انتخاب شده';

        if (selectedFileDiv) {
            selectedFileDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center p-3 rounded-2" style="background: rgba(255,255,255,0.03);">
                    <div class="d-flex align-items-center gap-3">
                        <div class="file-icon-small">
                            <i class="${getFileIcon(window.selectedDeliveryFile.name)}"></i>
                        </div>
                        <div>
                            <div class="small text-light fw-semibold file-name-display">${window.selectedDeliveryFile.name.length > 35 ? window.selectedDeliveryFile.name.substring(0, 35) + '...' : window.selectedDeliveryFile.name}</div>
                            <div class="small text-muted file-size-display">${formatFileSize(window.selectedDeliveryFile.size)}</div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-sm btn-link text-danger p-0 remove-single-file-btn">
                        <i class="fi-x"></i>
                    </button>
                </div>
            `;
        }

        document.querySelector('.remove-single-file-btn')?.addEventListener('click', function () {
            window.selectedDeliveryFile = null;
            if (fileInput) fileInput.value = '';
            updateSingleFileDisplay();
        });
    }

    if (dropzoneArea) {
        dropzoneArea.addEventListener('click', () => {
            if (fileInput) fileInput.click();
        });

        dropzoneArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzoneArea.classList.add('dragover');
        });

        dropzoneArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropzoneArea.classList.remove('dragover');
        });

        dropzoneArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzoneArea.classList.remove('dragover');
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                const file = files[0];
                const result = isValidFileType(file, serviceName);
                if (!result.valid) {
                    showMessage(result.message, 'error');
                    return;
                }
                window.selectedDeliveryFile = file;
                updateSingleFileDisplay();
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', function () {
            if (this.files.length > 0) {
                const file = this.files[0];
                const result = isValidFileType(file, serviceName);
                if (!result.valid) {
                    showMessage(result.message, 'error');
                    this.value = '';
                    return;
                }
                window.selectedDeliveryFile = file;
                updateSingleFileDisplay();
            }
        });
    }

    window.updateSingleFileDisplay = updateSingleFileDisplay;
})();