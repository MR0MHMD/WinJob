(function() {
    const deliveryForm = document.getElementById('deliveryForm');
    if (deliveryForm) {
        deliveryForm.addEventListener('submit', function(e) {
            e.preventDefault(); // جلوگیری از submit عادی

            const isMultiChoice = !!document.getElementById('multiDropzoneArea');
            const hiddenInput = document.getElementById('selectedFilesCountInput');
            const selectedCount = parseInt(hiddenInput?.value) || 0;

            if (isMultiChoice) {
                if (selectedCount === 0) {
                    showMessage('لطفاً حداقل یک فایل برای تحویل انتخاب کنید!', 'error');
                    return false;
                }
            } else {
                if (!window.selectedDeliveryFile) {
                    showMessage('لطفاً یک فایل برای تحویل انتخاب کنید!', 'error');
                    return false;
                }
            }

            // ========== ساخت FormData و اضافه کردن فایل‌ها ==========
            const formData = new FormData(deliveryForm);

            // اضافه کردن فایل‌های MULTI_CHOICE
            if (isMultiChoice && window.selectedMultiFiles.length > 0) {
                // حذف فایل‌های قبلی از formData (اگر وجود داشته باشن)
                formData.delete('delivery_files');

                window.selectedMultiFiles.forEach(file => {
                    formData.append('delivery_files', file);
                });
            }

            // اضافه کردن فایل SINGLE
            if (!isMultiChoice && window.selectedDeliveryFile) {
                formData.delete('delivery_file');
                formData.append('delivery_file', window.selectedDeliveryFile);
            }

            // ========== ارسال با fetch ==========
            const submitBtn = document.getElementById('deliverSubmitBtn');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fi-loading"></i> در حال ارسال...';
            submitBtn.disabled = true;

            const orderId = deliveryForm.action.split('/').filter(Boolean).pop();

            fetch(deliveryForm.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.error || 'خطا در ارسال') });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('deliveryModal'));
                    if (modal) modal.hide();
                    showMessage(data.message, 'success', () => {
                        location.reload();
                    });
                } else {
                    showMessage(data.error || 'خطا در تحویل سفارش', 'error');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('خطا در ارتباط با سرور: ' + error.message, 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });

            return false;
        });
    }
})();