// ============================================
// توابع کمکی - service_plans_helpers.js
// ============================================

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

function getCsrfToken() {
    const tokenInput = document.querySelector('#planForm [name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : '';
}

function showNotif(title, message, type = 'info') {
    if (typeof showNotificationModal === 'function') {
        const formattedMessage = message.replace(/\n/g, '<br>');
        showNotificationModal(title, formattedMessage, type);
    } else {
        alert(message);
    }
}

function escapeHtml(str) {
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// ========== ✅ جدید: نمایش/مخفی کردن فیلدهای quantity ==========
function toggleQuantityFields() {
    const pricingUnit = document.getElementById('pricingUnit');
    if (!pricingUnit) return;

    const unit = pricingUnit.value;
    const isTimeUnit = (unit === 'second' || unit === 'minute');

    // فیلدهای quantity
    const quantityFields = [
        { id: 'baseQuantity', label: 'مقدار پایه' },
        { id: 'minQuantity', label: 'حداقل مقدار' },
        { id: 'maxQuantity', label: 'حداکثر مقدار' }
    ];

    quantityFields.forEach(({ id, label }) => {
        const field = document.getElementById(id);
        if (!field) return;

        const wrapper = field.closest('.col-md-4');
        if (!wrapper) return;

        if (isTimeUnit) {
            wrapper.style.display = 'block';
            field.required = true;
            field.disabled = false;
        } else {
            wrapper.style.display = 'none';
            field.required = false;
            field.disabled = true;
            field.value = '';
        }
    });

    // به‌روزرسانی help text واحد قیمت‌گذاری
    const helpText = document.getElementById('pricingUnitHelp');
    if (helpText) {
        const unitLabels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'تعدادی'
        };
        const unitName = unitLabels[unit] || unit;
        if (isTimeUnit) {
            helpText.innerHTML = `
                <i class="fi-info-circle me-1"></i>
                برای واحد "<strong>${unitName}</strong>"، مقدار پایه، حداقل و حداکثر الزامی است.
            `;
        } else if (unit === 'quantity') {
            helpText.innerHTML = `
                <i class="fi-info-circle me-1"></i>
                برای واحد "<strong>تعدادی</strong>"، نیازی به مقدار پایه، حداقل و حداکثر نیست.
                تعداد فایل‌ها توسط <strong>نوع تحویل</strong> مشخص میشود.
            `;
        } else {
            helpText.innerHTML = `
                <i class="fi-info-circle me-1"></i>
                واحدهای مجاز برای این سرویس: ${window.ALLOWED_UNITS ? window.ALLOWED_UNITS.join('، ') : 'همه واحدها'}
            `;
        }
    }

    // به‌روزرسانی deliveryType
    if (typeof updateDeliveryTypeOptions === 'function') {
        updateDeliveryTypeOptions();
    }
}