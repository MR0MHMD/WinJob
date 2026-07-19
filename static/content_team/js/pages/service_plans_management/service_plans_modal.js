// ============================================
// مدیریت مودال - service_plans_modal.js
// ============================================

function initPlanModal() {
    const modal = document.getElementById('createPlanModal');
    if (!modal) return;

    modal.addEventListener('hidden.bs.modal', function() {
        // ========== ۱. ریست فرم ==========
        document.getElementById('planForm').reset();
        document.getElementById('planId').value = '';
        document.getElementById('planModalTitle').innerHTML = '<i class="fi-plus-circle me-2 text-primary"></i> ایجاد پلن جدید';

        // ========== ۲. ریست pricingUnit به حالت اولیه ==========
        const pricingUnitSelect = document.getElementById('pricingUnit');
        pricingUnitSelect.value = '';
        pricingUnitSelect.disabled = false;
        pricingUnitSelect.innerHTML = `
            <option value="">انتخاب کنید...</option>
            <option value="second">ثانیه</option>
            <option value="minute">دقیقه</option>
            <option value="quantity">تعدادی</option>
        `;

        // ========== ۳. ریست deliveryType ==========
        const deliveryTypeSelect = document.getElementById('deliveryType');
        deliveryTypeSelect.innerHTML = '';
        deliveryTypeSelect.disabled = true;
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'ابتدا واحد را انتخاب کنید';
        deliveryTypeSelect.appendChild(opt);
        deliveryTypeSelect.value = '';
        deliveryTypeSelect.removeAttribute('data-initial-value');

        // ========== ۴. ریست deliveryOptionsWrapper ==========
        document.getElementById('deliveryOptionsWrapper').style.display = 'none';
        document.getElementById('deliveryOptionsCount').value = '';

        // ========== ۵. ریست help‌ها ==========
        const unitLabels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'تعدادی'
        };
        const allowedUnits = window.ALLOWED_UNITS || [];
        let unitsDisplay = allowedUnits.map(u => unitLabels[u] || u).join('، ');
        if (!unitsDisplay) unitsDisplay = 'همه واحدها';

        document.getElementById('pricingUnitHelp').innerHTML = `
            <i class="fi-info-circle me-1"></i>
            واحدهای مجاز برای این سرویس: ${unitsDisplay}
        `;
        document.getElementById('deliveryTypeHelp').textContent = 'ابتدا واحد قیمت‌گذاری را انتخاب کنید.';

        // ========== ۶. ریست ویژگی‌ها ==========
        const container = document.getElementById('featuresContainer');
        container.innerHTML = '';
        if (typeof addFeature === 'function') {
            addFeature();
        }

        // ========== ۷. دوباره اجرای تابع initPlanForm ==========
        setTimeout(function() {
            if (typeof initPlanForm === 'function') {
                initPlanForm();
            }
        }, 100);
    });

    modal.setAttribute('data-create-url', window.location.pathname.replace('/management/', '/api/create/'));
}