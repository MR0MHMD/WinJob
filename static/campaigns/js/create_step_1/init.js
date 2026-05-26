"use strict";

document.addEventListener("DOMContentLoaded", function () {
    var dom = CampaignDOM;

    if (!dom.platformSelect || !dom.contentTypeSelect || !dom.adTypeSelect) {
        console.error("❌ المان‌های فرم پیدا نشدند");
        return;
    }

    buildCards(dom.platformSelect, dom.platformCards);

    // مخفی کردن همه چیز به جز پلتفرم
    hideAdType();
    hideContentType();
    hideServiceType();
    hideMinutes();
    hideDateAndName();

    // اگر پلتفرم از قبل انتخاب شده بود (حالت برگشت از خطا یا ویرایش)
    if (dom.platformSelect.value) {
        var platformId = dom.platformSelect.value;

        // بروزرسانی گزینه‌های نوع محتوا و نوع تبلیغ
        updateContentType(platformId);
        updateAdType(platformId);

        // نمایش نوع تبلیغ
        showAdType();

        // تعیین مقدار از پیش انتخاب شده برای نوع تبلیغ
        var presetAdType = CampaignData.PREV_AD_TYPE || (window.EDIT_MODE ? window.EDIT_AD_TYPE_ID : '');
        if (presetAdType) {
            dom.adTypeSelect.value = presetAdType;
            buildCards(dom.adTypeSelect, dom.adCards);
            showContentType();

            // تعیین مقدار از پیش انتخاب شده برای نوع محتوا
            var presetContentType = CampaignData.PREV_CONTENT || (window.EDIT_MODE ? window.EDIT_CONTENT_TYPE_ID : '');
            if (presetContentType) {
                dom.contentTypeSelect.value = presetContentType;
                buildCards(dom.contentTypeSelect, dom.contentCards);

                var currentMeta = CampaignData.CONTENT_TYPE_META[presetContentType];
                var currentSlug = currentMeta ? currentMeta.slug : null;

                // تنظیم محدودیت تاریخ بر اساس نوع محتوا
                if (window.CampaignDatepicker) {
                    window.CampaignDatepicker.setStartMinDays(currentSlug === "content-production-team" ? 10 : 2);
                }

                if (currentSlug === "content-production-team") {
                    updateServiceTypes(dom.adTypeSelect.value);
                    showServiceType();

                    var presetService = window.EDIT_MODE ? window.EDIT_SERVICE_TYPE_ID : '';
                    if (presetService && dom.serviceSelect) {
                        dom.serviceSelect.value = presetService;
                        buildCards(dom.serviceSelect, dom.serviceCards);

                        // انتخاب گزینه سرویس برای خواندن unit
                        var selectedService = dom.serviceSelect.options[dom.serviceSelect.selectedIndex];
                        if (selectedService && selectedService.dataset.unit === "minute") {
                            showMinutes();
                            // مقداردهی دقیقه - اولویت با مقدار فرم (که از initial آمده) سپس EDIT_MINUTES
                            var minutesVal = dom.minutesInput.value || window.EDIT_MINUTES;
                            if (minutesVal) {
                                dom.minutesInput.value = minutesVal;
                            }
                        } else if (selectedService && selectedService.dataset.unit !== "minute") {
                            hideMinutes();
                        }
                        showDateAndName();
                    } else {
                        // اگر سرویسی از قبل انتخاب نشده، فقط تاریخ و نام را نشان بده
                        showDateAndName();
                    }
                } else {
                    hideServiceType();
                    hideMinutes();
                    showDateAndName();
                }
            }
        }
    }

    registerListeners();
    initDatepicker();
    validateForm();
});