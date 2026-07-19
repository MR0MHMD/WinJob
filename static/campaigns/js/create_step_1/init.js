"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const dom = CampaignDOM;

    if (!dom.platformSelect || !dom.contentTypeSelect || !dom.adTypeSelect) {
        console.error("❌ المان‌های فرم پیدا نشدند");
        return;
    }

    buildCards(dom.platformSelect, dom.platformCards);

    // مخفی کردن همه چیز به جز پلتفرم
    hideAdType();
    hideContentType();
    hideServiceType();
    // ❌ حذف hideMinutes
    // hideMinutes();
    hideDateAndName();

    if (dom.platformSelect.value) {
        const platformId = dom.platformSelect.value;

        updateContentType(platformId);
        updateAdType(platformId);

        showAdType();

        const presetAdType = CampaignData.PREV_AD_TYPE || (window.EDIT_MODE ? window.EDIT_AD_TYPE_ID : '');
        if (presetAdType) {
            dom.adTypeSelect.value = presetAdType;
            buildCards(dom.adTypeSelect, dom.adCards);
            showContentType();

            if (CampaignDOM.freeCheckbox) {
                window.toggleFreeCampaign();
            }

            const presetContentType = CampaignData.PREV_CONTENT || (window.EDIT_MODE ? window.EDIT_CONTENT_TYPE_ID : '');
            if (presetContentType) {
                dom.contentTypeSelect.value = presetContentType;
                buildCards(dom.contentTypeSelect, dom.contentCards);

                const currentMeta = CampaignData.CONTENT_TYPE_META[presetContentType];
                const currentSlug = currentMeta ? currentMeta.slug : null;

                if (window.CampaignDatepicker) {
                    window.CampaignDatepicker.setStartMinDays(currentSlug === "content-production-team" ? 10 : 2);
                }

                if (currentSlug === "content-production-team") {
                    updateServiceTypes(dom.adTypeSelect.value);
                    showServiceType();

                    const presetService = window.EDIT_MODE ? window.EDIT_SERVICE_TYPE_ID : '';
                    if (presetService && dom.serviceSelect) {
                        dom.serviceSelect.value = presetService;
                        buildCards(dom.serviceSelect, dom.serviceCards);

                        // ========== نمایش واحدهای مجاز ==========
                        const serviceInfo = document.getElementById("service-type-info");
                        const unitsDisplay = document.getElementById("service-type-units-display");
                        if (serviceInfo && unitsDisplay) {
                            const meta = CampaignData.SERVICE_TYPE_META[presetService];
                            if (meta && meta.allowed_units_display) {
                                serviceInfo.style.display = "block";
                                unitsDisplay.textContent = "واحدهای مجاز: " + meta.allowed_units_display;
                            }
                        }

                        // ❌ حذف منطق minutes
                        // var selectedService = dom.serviceSelect.options[dom.serviceSelect.selectedIndex];
                        // if (selectedService && selectedService.dataset.unit === "minute") {
                        //     showMinutes();
                        //     var minutesVal = dom.minutesInput.value || window.EDIT_MINUTES;
                        //     if (minutesVal) {
                        //         dom.minutesInput.value = minutesVal;
                        //     }
                        // } else if (selectedService && selectedService.dataset.unit !== "minute") {
                        //     hideMinutes();
                        // }
                        showDateAndName();
                    } else {
                        showDateAndName();
                    }
                } else {
                    hideServiceType();
                    // ❌ حذف hideMinutes
                    // hideMinutes();
                    showDateAndName();
                }
            }
        }
    }

    registerListeners();
    initDatepicker();
    validateForm();
});