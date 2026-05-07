// ==================== توابع کمکی ====================

function formatDateInput(input) {
    let value = input.value.replace(/[^0-9]/g, '');
    if (value.length > 8) value = value.slice(0, 8);
    let formatted = '';
    if (value.length > 4) {
        formatted = value.slice(0, 4) + '/' + value.slice(4, 6) + '/' + value.slice(6, 8);
    } else if (value.length > 2) {
        formatted = value.slice(0, 4) + '/' + value.slice(4);
    } else {
        formatted = value;
    }
    input.value = formatted;
}

function formatTimeInput(input) {
    let value = input.value.replace(/[^0-9]/g, '');
    if (value.length > 4) value = value.slice(0, 4);
    let formatted = '';
    if (value.length > 2) {
        formatted = value.slice(0, 2) + ':' + value.slice(2, 4);
    } else {
        formatted = value;
    }
    input.value = formatted;
}

function generateRandomCode() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 8; i++) {
        code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    document.getElementById('couponCode').value = code;
}

function toggleDiscountValue(type) {
    const label = document.getElementById('discountValueLabel');
    const hint = document.getElementById('discountValueHint');
    const input = document.getElementById('discountValue');

    if (type === 'percentage') {
        label.textContent = 'درصد تخفیف';
        hint.textContent = 'عددی بین ۱ تا ۱۰۰';
        input.placeholder = 'مثلاً: ۲۰';
    } else if (type === 'fixed') {
        label.textContent = 'مبلغ تخفیف (تومان)';
        hint.textContent = 'مبلغ را به تومان وارد کنید';
        input.placeholder = 'مثلاً: ۵۰۰۰۰';
    }
}

function formatNumberInput(input) {
    let value = input.value.replace(/,/g, '');

    if (value === '') {
        input.value = '';
        return;
    }

    let number = parseInt(value, 10);
    if (isNaN(number)) {
        input.value = value;
        return;
    }

    input.value = number.toLocaleString('en-US');
}

// ==================== اعتبارسنجی ====================

function validateDateTime(dateValue, timeValue) {
    // اگه تاریخ خالیه، زمانم خالی باشه مشکلی نیست
    if (!dateValue && !timeValue) return true;

    // اگه تاریخ هست ولی خالیه، زمان مهم نیست
    if (!dateValue) return true;

    // اعتبارسنجی تاریخ: 1405/02/21
    const datePattern = /^1[34]\d{2}\/(0[1-9]|1[0-2])\/(0[1-9]|[12]\d|3[01])$/;
    if (!datePattern.test(dateValue)) {
        return false;
    }

    // اعتبارسنجی زمان: 18:19 (فقط اگه وارد شده)
    if (timeValue) {
        const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;
        if (!timePattern.test(timeValue)) {
            return false;
        }
    }

    return true;
}

// ==================== مودال ساخت ====================

function openCreateModal() {
    document.getElementById('couponForm').reset();
    document.getElementById('couponId').value = '';
    document.getElementById('couponForm').action = "/influencers/coupons/create/";

    document.getElementById('couponModalTitle').innerHTML =
        '<i class="fi-plus-circle text-primary ms-1"></i> ساخت کد تخفیف جدید';

    document.getElementById('couponSubmitBtn').innerHTML =
        '<i class="fi-check ms-1"></i> ساخت کد تخفیف';
    document.getElementById('couponSubmitBtn').className = 'btn btn-primary';

    document.getElementById('activeSwitchWrapper').style.display = 'none';
    document.getElementById('discountValue').value = '';
    document.getElementById('maxUses').value = '';

    let modal = new bootstrap.Modal(document.getElementById('couponModal'));
    modal.show();
}

// ==================== مودال ویرایش ====================

document.querySelectorAll('.edit-coupon-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
        let couponId = this.dataset.id;
        let code = this.dataset.code;
        let discountType = this.dataset.discountType;
        let value = this.dataset.value;
        let channelId = this.dataset.channelId;
        let maxUses = this.dataset.maxUses;
        let expiresDate = this.dataset.expiresDate;
        let expiresTime = this.dataset.expiresTime;
        let isActive = this.dataset.isActive;

        document.getElementById('couponForm').action = "/influencers/coupons/" + couponId + "/edit/";
        document.getElementById('couponId').value = couponId;
        document.getElementById('couponCode').value = code;
        document.getElementById('discountType').value = discountType;
        document.getElementById('discountValue').value = value;
        document.getElementById('channelSelect').value = channelId;
        document.getElementById('maxUses').value = maxUses;
        document.getElementById('expiresDate').value = expiresDate;
        document.getElementById('expiresTime').value = expiresTime;
        document.getElementById('activeSwitch').checked = (isActive === 'true');
        document.getElementById('activeSwitchWrapper').style.display = 'block';

        toggleDiscountValue(discountType);

        document.getElementById('couponModalTitle').innerHTML =
            '<i class="fi-edit text-warning ms-1"></i> ویرایش کد تخفیف';

        document.getElementById('couponSubmitBtn').innerHTML =
            '<i class="fi-check ms-1"></i> ذخیره تغییرات';
        document.getElementById('couponSubmitBtn').className = 'btn btn-warning';

        let modal = new bootstrap.Modal(document.getElementById('couponModal'));
        modal.show();
    });
});

// ==================== حذف ====================

function confirmDelete(couponId, couponCode) {
    document.getElementById('deleteCodeName').textContent = 'کد: ' + couponCode;
    document.getElementById('deleteCouponForm').action = "/influencers/coupons/" + couponId + "/delete/";

    let deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    deleteModal.show();
}

// ==================== سابمیت فرم ====================

document.getElementById('couponForm').addEventListener('submit', function (e) {
    const dateInput = document.getElementById('expiresDate');
    const timeInput = document.getElementById('expiresTime');
    const discountValue = document.getElementById('discountValue');
    const maxUses = document.getElementById('maxUses');

    // حذف کاماها
    discountValue.value = discountValue.value.replace(/,/g, '');
    maxUses.value = maxUses.value.replace(/,/g, '');

    // اعتبارسنجی
    if (!validateDateTime(dateInput.value, timeInput.value)) {
        e.preventDefault();
        alert('فرمت تاریخ یا ساعت اشتباه است!\n\n📅 تاریخ: ۱۴۰۵/۰۲/۰۶\n⏰ ساعت: ۱۴:۳۰');
        return;
    }
});