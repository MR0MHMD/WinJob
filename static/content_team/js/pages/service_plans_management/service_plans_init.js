// ============================================
// تنظیمات اولیه فرم - service_plans_init.js
// ============================================

function initPlanForm() {
    const deliveryType = document.getElementById('deliveryType');
    const optionsWrapper = document.getElementById('deliveryOptionsWrapper');

    function toggleDeliveryOptions() {
        if (deliveryType.value === 'multi_choice') {
            optionsWrapper.style.display = 'block';
        } else {
            optionsWrapper.style.display = 'none';
            document.getElementById('deliveryOptionsCount').value = '';
        }
    }

    // حذف لیسنرهای قبلی
    const newDeliveryType = deliveryType.cloneNode(true);
    deliveryType.parentNode.replaceChild(newDeliveryType, deliveryType);

    const newDeliveryTypeEl = document.getElementById('deliveryType');
    const newOptionsWrapper = document.getElementById('deliveryOptionsWrapper');

    newDeliveryTypeEl.addEventListener('change', function() {
        if (this.value === 'multi_choice') {
            newOptionsWrapper.style.display = 'block';
        } else {
            newOptionsWrapper.style.display = 'none';
            document.getElementById('deliveryOptionsCount').value = '';
        }
    });

    if (newDeliveryTypeEl.value === 'multi_choice') {
        newOptionsWrapper.style.display = 'block';
    } else {
        newOptionsWrapper.style.display = 'none';
    }

    // ========== محدود کردن واحدها بر اساس سرویس ==========
    const allowedUnits = window.ALLOWED_UNITS || [];
    const pricingUnitSelect = document.getElementById('pricingUnit');
    const pricingUnitHelp = document.getElementById('pricingUnitHelp');
    const deliveryTypeSelect = document.getElementById('deliveryType');
    const deliveryTypeHelp = document.getElementById('deliveryTypeHelp');

    if (allowedUnits && allowedUnits.length > 0) {
        Array.from(pricingUnitSelect.options).forEach(option => {
            if (option.value && !allowedUnits.includes(option.value)) {
                option.disabled = true;
                option.style.display = 'none';
            }
        });

        if (allowedUnits.length === 1) {
            const unit = allowedUnits[0];
            pricingUnitSelect.value = unit;
            pricingUnitSelect.disabled = true;

            const unitLabels = {
                'second': 'ثانیه',
                'minute': 'دقیقه',
                'quantity': 'تعدادی'
            };
            pricingUnitHelp.innerHTML = `
                <i class="fi-info-circle me-1"></i>
                این سرویس فقط از واحد "<strong>${unitLabels[unit]}</strong>" پشتیبانی میکند.
            `;

            if (deliveryTypeSelect) {
                deliveryTypeSelect.innerHTML = '';

                if (unit === 'second' || unit === 'minute') {
                    const opt = document.createElement('option');
                    opt.value = 'single';
                    opt.textContent = '📤 تحویل یک فایل';
                    deliveryTypeSelect.appendChild(opt);
                    deliveryTypeSelect.value = 'single';
                    deliveryTypeSelect.disabled = true;
                    deliveryTypeSelect.setAttribute('data-initial-value', 'single');

                    if (deliveryTypeHelp) {
                        deliveryTypeHelp.textContent = 'برای واحد ثانیه/دقیقه، فقط "تحویل یک فایل" مجاز است.';
                    }

                    const wrapper = document.getElementById('deliveryOptionsWrapper');
                    if (wrapper) wrapper.style.display = 'none';

                } else if (unit === 'quantity') {
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

                    deliveryTypeSelect.value = 'single';
                    deliveryTypeSelect.disabled = false;
                    deliveryTypeSelect.setAttribute('data-initial-value', 'single');

                    if (deliveryTypeHelp) {
                        deliveryTypeHelp.textContent = 'برای خدمات تعدادی، می‌توانید نوع تحویل را انتخاب کنید.';
                    }

                    const wrapper = document.getElementById('deliveryOptionsWrapper');
                    if (wrapper) wrapper.style.display = 'none';
                }
            }
        }
    }

    // ========== ✅ اجرای toggleQuantityFields ==========
    if (typeof toggleQuantityFields === 'function') {
        setTimeout(function() {
            toggleQuantityFields();
        }, 50);
    }

    if (typeof updateDeliveryTypeOptions === 'function') {
        setTimeout(function() {
            updateDeliveryTypeOptions();
        }, 100);
    }
}