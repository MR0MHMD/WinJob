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

    // اگر پلتفرم از قبل انتخاب شده بود (حالت برگشت از خطا)
    if (dom.platformSelect.value) {
        var platformId = dom.platformSelect.value;

        // بروزرسانی گزینه‌ها
        updateContentType(platformId);
        updateAdType(platformId);

        // نمایش نوع تبلیغ
        showAdType();

        // اگر نوع تبلیغ قبلاً انتخاب شده بود
        if (CampaignData.PREV_AD_TYPE) {
            dom.adTypeSelect.value = CampaignData.PREV_AD_TYPE;
            buildCards(dom.adTypeSelect, dom.adCards);

            // نمایش نوع محتوا
            showContentType();

            if (CampaignData.PREV_CONTENT) {
                dom.contentTypeSelect.value = CampaignData.PREV_CONTENT;
                buildCards(dom.contentTypeSelect, dom.contentCards);

                var currentMeta = CampaignData.CONTENT_TYPE_META[CampaignData.PREV_CONTENT];
                var currentSlug = currentMeta ? currentMeta.slug : null;

                // تنظیم محدودیت تاریخ
                if (window.CampaignDatepicker) {
                    window.CampaignDatepicker.setStartMinDays(currentSlug === "content-production-team" ? 10 : 2);
                }

                if (currentSlug === "content-production-team") {
                    updateServiceTypes(dom.adTypeSelect.value);
                    showServiceType();

                    if (dom.serviceSelect && dom.serviceSelect.value) {
                        var selectedService = dom.serviceSelect.options[dom.serviceSelect.selectedIndex];
                        if (selectedService && selectedService.dataset.unit === "minute") {
                            showMinutes();
                        }
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
    validateForm()
});