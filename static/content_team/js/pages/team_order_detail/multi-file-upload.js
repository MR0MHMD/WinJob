(function() {
    const multiDropzone = document.getElementById('multiDropzoneArea');
    const multiFileInput = document.getElementById('multiFileInput');
    const multiSelectedContainer = document.getElementById('multiSelectedFilesContainer');
    const multiSelectedFilesDiv = document.getElementById('multiSelectedFiles');
    const multiDropzoneText = document.getElementById('multiDropzoneText');
    const selectedFilesCount = document.getElementById('selectedFilesCount');
    const modalBody = document.getElementById('deliveryModalBody');
    const serviceName = modalBody ? modalBody.dataset.serviceName : '';

    window.selectedMultiFiles = [];
    let requiredCount = 0;

    if (modalBody) {
        requiredCount = parseInt(modalBody.dataset.requiredCount) || 0;
    }

    if (multiDropzone && requiredCount === 0) {
        const text = multiDropzone.querySelector('.text-primary')?.textContent || '';
        const match = text.match(/(\d+)/);
        if (match) {
            requiredCount = parseInt(match[0]) || 0;
        }
    }

    function updateMultiFilesDisplay() {
        const hasFiles = window.selectedMultiFiles.length > 0;

        if (!hasFiles) {
            if (multiSelectedContainer) multiSelectedContainer.style.display = 'none';
            if (multiDropzoneText) {
                multiDropzoneText.innerHTML = `
                    برای آپلود کلیک کنید یا فایل‌ها را بکشید
                    <br>
                    <span class="text-primary">(${requiredCount} فایل مورد نیاز)</span>
                `;
            }
            return;
        }

        if (multiSelectedContainer) multiSelectedContainer.style.display = 'block';
        if (selectedFilesCount) selectedFilesCount.textContent = window.selectedMultiFiles.length;
        if (multiDropzoneText) {
            multiDropzoneText.innerHTML = `${window.selectedMultiFiles.length} از ${requiredCount} فایل انتخاب شده`;
        }

        if (multiSelectedFilesDiv) {
            let html = '';
            window.selectedMultiFiles.forEach((file, index) => {
                html += `
                    <div class="selected-file-item">
                        <div class="file-info-wrap">
                            <div class="file-icon-small">
                                <i class="${getFileIcon(file.name)}"></i>
                            </div>
                            <div>
                                <div class="file-name-display">${file.name.length > 35 ? file.name.substring(0, 35) + '...' : file.name}</div>
                                <div class="file-size-display">${formatFileSize(file.size)}</div>
                            </div>
                        </div>
                        <button type="button" class="btn-remove-file remove-multi-file-btn" data-index="${index}">
                            <i class="fi-x"></i>
                        </button>
                    </div>
                `;
            });
            multiSelectedFilesDiv.innerHTML = html;
        }

        document.querySelectorAll('.remove-multi-file-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.dataset.index);
                window.selectedMultiFiles.splice(index, 1);
                updateMultiFilesDisplay();
                updateMultiSubmitBtn();
            });
        });

        updateMultiSubmitBtn();
    }

    function updateMultiSubmitBtn() {
        const submitBtn = document.getElementById('deliverSubmitBtn');
        const hiddenInput = document.getElementById('selectedFilesCountInput');
        if (!submitBtn) return;

        const count = window.selectedMultiFiles.length;

        // ✅ به‌روزرسانی hidden input با تعداد فایل‌های انتخاب شده
        if (hiddenInput) {
            hiddenInput.value = count;
        }

        console.log('📁 selectedMultiFiles:', count, 'required:', requiredCount);

        if (count === requiredCount && requiredCount > 0) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fi-upload me-2"></i> تحویل سفارش';
        } else {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<i class="fi-upload me-2"></i> ${count}/${requiredCount} فایل`;
        }
    }

    function handleMultiFiles(newFiles) {
        for (const file of newFiles) {
            const result = isValidFileType(file, serviceName);
            if (!result.valid) {
                showMessage(result.message, 'error');
                return;
            }
        }

        const allFiles = [...window.selectedMultiFiles, ...newFiles];
        if (allFiles.length > requiredCount) {
            showMessage(`حداکثر ${requiredCount} فایل می‌توانید آپلود کنید.`, 'error');
            return;
        }
        window.selectedMultiFiles = allFiles;
        updateMultiFilesDisplay();
    }

    if (multiDropzone) {
        multiDropzone.addEventListener('click', () => {
            if (multiFileInput) multiFileInput.click();
        });

        multiDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            multiDropzone.classList.add('dragover');
        });

        multiDropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            multiDropzone.classList.remove('dragover');
        });

        multiDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            multiDropzone.classList.remove('dragover');
            const files = Array.from(e.dataTransfer.files);
            handleMultiFiles(files);
        });
    }

    if (multiFileInput) {
        multiFileInput.addEventListener('change', function() {
            const files = Array.from(this.files);
            handleMultiFiles(files);
            this.value = '';
        });
    }

    if (document.querySelector('#multiDropzoneArea')) {
        updateMultiSubmitBtn();
    }

    window.updateMultiFilesDisplay = updateMultiFilesDisplay;
    window.updateMultiSubmitBtn = updateMultiSubmitBtn;
    window.handleMultiFiles = handleMultiFiles;
})();