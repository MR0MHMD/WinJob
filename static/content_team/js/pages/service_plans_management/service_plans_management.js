// ============================================
// مدیریت پلن‌ها - service_plans_management.js
// ============================================

(function () {
    'use strict';

    // ---------- مدیریت ویژگی‌ها ----------
    window.addFeature = function () {
        const container = document.getElementById('featuresContainer');
        const div = document.createElement('div');
        div.className = 'spm-feature-item';
        div.innerHTML = `
            <input type="text" class="spm-feature-input" placeholder="مثال: ۲ دوربین 4K">
            <button type="button" class="remove-feature" onclick="removeFeature(this)"><i class="fi-trash"></i></button>
        `;
        container.appendChild(div);
    };

    window.removeFeature = function (btn) {
        const container = document.getElementById('featuresContainer');
        if (container.children.length > 1) {
            btn.closest('.spm-feature-item').remove();
        } else {
            showNotif('توجه', 'حداقل یک ویژگی باید وجود داشته باشد', 'warning');
        }
    };

    function addFeatureWithValue(value) {
        const container = document.getElementById('featuresContainer');
        const div = document.createElement('div');
        div.className = 'spm-feature-item';
        div.innerHTML = `
            <input type="text" class="spm-feature-input" value="${escapeHtml(value)}" placeholder="مثال: ۲ دوربین 4K">
            <button type="button" class="remove-feature" onclick="removeFeature(this)"><i class="fi-trash"></i></button>
        `;
        container.appendChild(div);
    }

    // ============================================================
    // ✅ اصلاح: تابع updateDeliveryTypeOptions
    // ============================================================
    window.updateDeliveryTypeOptions = function () {
        const pricingUnitSelect = document.getElementById('pricingUnit');
        const deliveryTypeSelect = document.getElementById('deliveryType');
        const deliveryOptionsWrapper = document.getElementById('deliveryOptionsWrapper');
        const deliveryTypeHelp = document.getElementById('deliveryTypeHelp');

        if (!pricingUnitSelect || !deliveryTypeSelect) return;

        let unit = pricingUnitSelect.value;

        if (!unit && pricingUnitSelect.disabled) {
            const options = pricingUnitSelect.querySelectorAll('option');
            for (let opt of options) {
                if (opt.value && !opt.disabled && opt.style.display !== 'none') {
                    unit = opt.value;
                    break;
                }
            }
        }

        deliveryTypeSelect.innerHTML = '';

        if (unit === 'second' || unit === 'minute') {
            // ✅ فقط SINGLE مجاز است
            const opt = document.createElement('option');
            opt.value = 'single';
            opt.textContent = '📤 تحویل یک فایل';
            deliveryTypeSelect.appendChild(opt);
            deliveryTypeSelect.value = 'single';
            deliveryTypeSelect.disabled = true;

            if (deliveryOptionsWrapper) {
                deliveryOptionsWrapper.style.display = 'none';
                document.getElementById('deliveryOptionsCount').value = '';
            }
            if (deliveryTypeHelp) {
                deliveryTypeHelp.textContent = 'برای واحد ثانیه/دقیقه، فقط "تحویل یک فایل" مجاز است.';
            }

        } else if (unit === 'quantity') {
            // ✅ فقط SINGLE و MULTI_CHOICE مجاز است
            const options = [
                {value: 'single', text: '📤 تحویل یک فایل'},
                {value: 'multi_choice', text: '🎨 چند گزینه برای انتخاب'}
            ];
            options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;
                deliveryTypeSelect.appendChild(option);
            });

            deliveryTypeSelect.disabled = false;

            const initialValue = deliveryTypeSelect.getAttribute('data-initial-value');
            if (initialValue && ['single', 'multi_choice'].includes(initialValue)) {
                deliveryTypeSelect.value = initialValue;
            } else {
                deliveryTypeSelect.value = 'single';
            }

            if (deliveryTypeHelp) {
                deliveryTypeHelp.textContent = 'برای خدمات تعدادی، می‌توانید نوع تحویل را انتخاب کنید.';
            }

            if (deliveryTypeSelect.value === 'multi_choice' && deliveryOptionsWrapper) {
                deliveryOptionsWrapper.style.display = 'block';
            } else if (deliveryOptionsWrapper) {
                deliveryOptionsWrapper.style.display = 'none';
                document.getElementById('deliveryOptionsCount').value = '';
            }

        } else {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'ابتدا واحد را انتخاب کنید';
            deliveryTypeSelect.appendChild(opt);
            deliveryTypeSelect.value = '';
            deliveryTypeSelect.disabled = true;

            if (deliveryOptionsWrapper) {
                deliveryOptionsWrapper.style.display = 'none';
            }
            if (deliveryTypeHelp) {
                deliveryTypeHelp.textContent = 'ابتدا واحد قیمت‌گذاری را انتخاب کنید.';
            }
        }

        deliveryTypeSelect.setAttribute('data-initial-value', deliveryTypeSelect.value);
    };

    // ============================================================
    // ✅ اصلاح: تابع getFormData
    // ============================================================
    function getFormData() {
        const formData = new FormData();

        formData.append('name', document.getElementById('planName').value);
        formData.append('description', document.getElementById('planDescription').value);
        formData.append('estimated_delivery_days', document.getElementById('planDelivery').value);
        formData.append('is_active', document.getElementById('planActive').checked ? 'on' : '');

        const pricingUnit = document.getElementById('pricingUnit').value;
        formData.append('pricing_unit', pricingUnit);

        // ========== ✅ فقط برای SECOND و MINUTE ارسال کن ==========
        if (pricingUnit === 'second' || pricingUnit === 'minute') {
            formData.append('base_quantity', document.getElementById('baseQuantity').value);
            formData.append('min_quantity', document.getElementById('minQuantity').value);
            const maxQuantity = document.getElementById('maxQuantity').value;
            if (maxQuantity) {
                formData.append('max_quantity', maxQuantity);
            }
        } else {
            // برای QUANTITY این فیلدها رو نال می‌فرستیم
            formData.append('base_quantity', '');
            formData.append('min_quantity', '');
            formData.append('max_quantity', '');
        }

        formData.append('delivery_type', document.getElementById('deliveryType').value);

        const deliveryOptionsCount = document.getElementById('deliveryOptionsCount').value;
        if (deliveryOptionsCount) {
            formData.append('delivery_options_count', deliveryOptionsCount);
        }

        const rawPrice = getRawPriceValue('planPrice');
        if (!rawPrice && rawPrice !== 0) {
            showNotif('خطا', 'لطفاً قیمت را وارد کنید', 'error');
            return null;
        }
        formData.append('price', rawPrice);

        const features = [];
        document.querySelectorAll('.spm-feature-input').forEach(inp => {
            if (inp.value.trim()) features.push(inp.value.trim());
        });
        features.forEach(f => formData.append('features', f));

        return formData;
    }

    // ============================================================
    // ذخیره (ایجاد/ویرایش)
    // ============================================================
    const submitBtn = document.getElementById('submitPlanBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', function() {
            const planId = document.getElementById('planId').value;
            let url;
            if (planId) {
                const activeCard = document.querySelector(`.spm-plan-card[data-plan-id="${planId}"]`);
                if (activeCard) url = activeCard.dataset.editUrl;
                else url = `/content_team/plans/api/edit/${planId}/`;
            } else {
                url = document.getElementById('createPlanModal').getAttribute('data-create-url') || '';
                if (!url) url = window.location.pathname.replace('/management/', '/api/create/');
            }
            if (!url) {
                showNotif('خطا', 'آدرس API مشخص نیست', 'error');
                return;
            }

            const formData = getFormData();
            if (!formData) return;

            submitBtn.disabled = true;
            submitBtn.textContent = 'در حال ذخیره...';

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showNotif('موفق', data.message, 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    let errorMessage = '';
                    if (data.errors) {
                        const fieldLabels = {
                            'name': 'نام پلن',
                            'price': 'قیمت',
                            'pricing_unit': 'واحد قیمت‌گذاری',
                            'base_quantity': 'مقدار پایه',
                            'min_quantity': 'حداقل مقدار',
                            'max_quantity': 'حداکثر مقدار',
                            'delivery_type': 'نوع تحویل',
                            'delivery_options_count': 'تعداد گزینه‌های تحویلی',
                            'estimated_delivery_days': 'مدت تحویل'
                        };
                        let errorList = [];
                        for (const [field, errors] of Object.entries(data.errors)) {
                            const label = fieldLabels[field] || field;
                            if (Array.isArray(errors)) {
                                errors.forEach(err => errorList.push(`• ${label}: ${err}`));
                            } else {
                                errorList.push(`• ${label}: ${errors}`);
                            }
                        }
                        if (data.message) {
                            errorMessage = data.message + '\n\n';
                        }
                        errorMessage += errorList.join('\n');
                    } else {
                        errorMessage = data.message || data.error || 'خطا در ذخیره پلن';
                    }
                    showNotif('⚠️ خطا در فرم', errorMessage, 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showNotif('خطا', 'خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.', 'error');
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = 'ذخیره پلن';
            });
        });
    }

    // ============================================================
    // ویرایش پلن
    // ============================================================
    window.editPlan = function (btn) {
        const card = btn.closest('.spm-plan-card');
        const planId = card.dataset.planId;
        const url = card.dataset.editUrl;
        fetch(url)
            .then(res => res.json())
            .then(data => {
                if (data.plan) {
                    document.getElementById('planModalTitle').innerHTML = '<i class="fi-edit me-2 text-primary"></i> ویرایش پلن';
                    document.getElementById('planId').value = planId;
                    document.getElementById('planName').value = data.plan.name;
                    document.getElementById('planDescription').value = data.plan.description || '';
                    document.getElementById('planPrice').value = Number(data.plan.price).toLocaleString('en-US');
                    document.getElementById('planDelivery').value = data.plan.estimated_delivery_days;
                    document.getElementById('planActive').checked = data.plan.is_active;

                    document.getElementById('pricingUnit').value = data.plan.pricing_unit || '';

                    // ========== ✅ ست کردن quantity فیلدها ==========
                    const isTimeUnit = (data.plan.pricing_unit === 'second' || data.plan.pricing_unit === 'minute');
                    if (isTimeUnit) {
                        document.getElementById('baseQuantity').value = data.plan.base_quantity || 1;
                        document.getElementById('minQuantity').value = data.plan.min_quantity || 1;
                        document.getElementById('maxQuantity').value = data.plan.max_quantity || '';
                    } else {
                        document.getElementById('baseQuantity').value = '';
                        document.getElementById('minQuantity').value = '';
                        document.getElementById('maxQuantity').value = '';
                    }

                    const deliveryTypeSelect = document.getElementById('deliveryType');
                    const deliveryValue = data.plan.delivery_type || 'single';
                    deliveryTypeSelect.setAttribute('data-initial-value', deliveryValue);
                    document.getElementById('deliveryOptionsCount').value = data.plan.delivery_options_count || '';

                    // ========== ✅ اجرای توابع ==========
                    if (typeof toggleQuantityFields === 'function') {
                        toggleQuantityFields();
                    }
                    if (typeof updateDeliveryTypeOptions === 'function') {
                        updateDeliveryTypeOptions();
                    }

                    const container = document.getElementById('featuresContainer');
                    container.innerHTML = '';
                    if (data.plan.features && data.plan.features.length) {
                        data.plan.features.forEach(f => addFeatureWithValue(f));
                    } else {
                        window.addFeature();
                    }

                    new bootstrap.Modal(document.getElementById('createPlanModal')).show();
                } else {
                    showNotif('خطا', 'خطا در دریافت اطلاعات پلن', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showNotif('خطا', 'خطا در دریافت اطلاعات', 'error');
            });
    };

    // ============================================================
    // حذف پلن
    // ============================================================
    window.deletePlan = function (btn) {
        const card = btn.closest('.spm-plan-card');
        const planId = card.dataset.planId;
        const deleteUrl = card.dataset.deleteUrl;

        document.getElementById('deletePlanId').value = planId;
        document.getElementById('deleteConfirmModal').setAttribute('data-delete-url', deleteUrl);

        const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        deleteModal.show();
    };

    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function () {
            const planId = document.getElementById('deletePlanId').value;
            const modalEl = document.getElementById('deleteConfirmModal');
            const deleteUrl = modalEl.getAttribute('data-delete-url');

            if (!deleteUrl) {
                showNotif('خطا', 'آدرس حذف مشخص نیست', 'error');
                return;
            }

            fetch(deleteUrl, {
                method: 'POST',
                headers: {'X-CSRFToken': getCsrfToken()}
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showNotif('موفق', data.message, 'success');
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        showNotif('خطا', data.error, 'error');
                    }
                })
                .catch(err => {
                    console.error(err);
                    showNotif('خطا', 'خطا در ارتباط با سرور', 'error');
                })
                .finally(() => {
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                });
        });
    }

    // ============================================================
    // رویداد تغییر pricingUnit
    // ============================================================
    const pricingUnitEl = document.getElementById('pricingUnit');
    if (pricingUnitEl) {
        pricingUnitEl.addEventListener('change', function () {
            if (typeof toggleQuantityFields === 'function') {
                toggleQuantityFields();
            }
            if (typeof updateDeliveryTypeOptions === 'function') {
                updateDeliveryTypeOptions();
            }
        });
    }

})();