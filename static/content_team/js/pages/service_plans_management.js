// ============================================
// مدیریت پلن‌ها - نسخه نهایی بدون toggle و با مودال حذف
// ============================================
(function() {
    'use strict';

    function getCsrfToken() {
        const tokenInput = document.querySelector('#planForm [name=csrfmiddlewaretoken]');
        return tokenInput ? tokenInput.value : '';
    }

    function showNotif(title, message, type = 'info') {
        if (typeof showNotificationModal === 'function') {
            showNotificationModal(title, message, type);
        } else {
            alert(message);
        }
    }

    // ---------- مدیریت ویژگی‌ها ----------
    window.addFeature = function() {
        const container = document.getElementById('featuresContainer');
        const div = document.createElement('div');
        div.className = 'spm-feature-item';
        div.innerHTML = `
            <input type="text" class="spm-feature-input" placeholder="مثال: ۲ دوربین 4K">
            <button type="button" class="remove-feature" onclick="removeFeature(this)"><i class="fi-trash"></i></button>
        `;
        container.appendChild(div);
    };

    window.removeFeature = function(btn) {
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

    function escapeHtml(str) {
        return str.replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    // ---------- ذخیره (ایجاد/ویرایش) ----------
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

            const formData = new FormData();
            formData.append('name', document.getElementById('planName').value);
            formData.append('description', document.getElementById('planDescription').value);

            const rawPrice = window.getRawPriceValue ? window.getRawPriceValue('planPrice') : 0;
            if (!rawPrice && rawPrice !== 0) {
                showNotif('خطا', 'لطفاً قیمت را وارد کنید', 'error');
                return;
            }
            formData.append('price_per_unit', rawPrice);

            formData.append('estimated_delivery_days', document.getElementById('planDelivery').value);
            formData.append('is_active', document.getElementById('planActive').checked ? 'on' : '');

            const features = [];
            document.querySelectorAll('.spm-feature-input').forEach(inp => {
                if (inp.value.trim()) features.push(inp.value.trim());
            });
            features.forEach(f => formData.append('features', f));

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
                    showNotif('خطا', data.error || 'خطا در ذخیره پلن', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showNotif('خطا', 'خطا در ارتباط با سرور', 'error');
            });
        });
    }

    // ---------- ویرایش پلن ----------
    window.editPlan = function(btn) {
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
                    document.getElementById('planPrice').value = Number(data.plan.price_per_unit).toLocaleString('en-US');
                    document.getElementById('planDelivery').value = data.plan.estimated_delivery_days;
                    document.getElementById('planActive').checked = data.plan.is_active;

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

    // ---------- حذف پلن (با مودال تأیید) ----------
    window.deletePlan = function(btn) {
        const card = btn.closest('.spm-plan-card');
        const planId = card.dataset.planId;
        const deleteUrl = card.dataset.deleteUrl;

        // تنظیم اطلاعات در مودال حذف
        document.getElementById('deletePlanId').value = planId;
        document.getElementById('deleteConfirmModal').setAttribute('data-delete-url', deleteUrl);

        const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        deleteModal.show();
    };

    // رویداد کلیک روی دکمه تأیید حذف در مودال
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function() {
            const planId = document.getElementById('deletePlanId').value;
            const modalEl = document.getElementById('deleteConfirmModal');
            const deleteUrl = modalEl.getAttribute('data-delete-url');

            if (!deleteUrl) {
                showNotif('خطا', 'آدرس حذف مشخص نیست', 'error');
                return;
            }

            fetch(deleteUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() }
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

    // ---------- ریست مودال بعد از بسته شدن ----------
    const modal = document.getElementById('createPlanModal');
    if (modal) {
        modal.addEventListener('hidden.bs.modal', function() {
            document.getElementById('planForm').reset();
            document.getElementById('planId').value = '';
            document.getElementById('planModalTitle').innerHTML = '<i class="fi-plus-circle me-2 text-primary"></i> ایجاد پلن جدید';
            const container = document.getElementById('featuresContainer');
            container.innerHTML = '';
            window.addFeature();
        });
        modal.setAttribute('data-create-url', window.location.pathname.replace('/management/', '/api/create/'));
    }
})();

function formatNumberInput(input) {
    let raw = input.value.replace(/[^0-9]/g, '');
    input.value = raw === '' ? '' : parseInt(raw, 10).toLocaleString('en-US');
}

function setupPriceFormatting(fieldId) {
    const priceField = document.getElementById(fieldId);
    if (priceField) {
        priceField.addEventListener('input', function() {
            formatNumberInput(this);
        });
    }
}

function getRawPriceValue(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return 0;
    let raw = field.value.replace(/,/g, '');
    return parseInt(raw, 10) || 0;
}

document.addEventListener('DOMContentLoaded', function() {
    setupPriceFormatting('planPrice');
});