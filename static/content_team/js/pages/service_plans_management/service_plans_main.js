document.addEventListener('DOMContentLoaded', function () {
    // تنظیم قیمت
    setupPriceFormatting('planPrice');

    // تنظیم اولیه فرم
    initPlanForm();

    // تنظیم مودال
    initPlanModal();

    // بروزرسانی نهایی
    setTimeout(function () {
        if (typeof updateDeliveryTypeOptions === 'function') {
            updateDeliveryTypeOptions();
        }
    }, 150);
});