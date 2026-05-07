"use strict";

document.addEventListener("DOMContentLoaded", function () {

    var dom = CampaignDOM;

    if (!dom.platformSelect || !dom.contentTypeSelect || !dom.adTypeSelect) {

        console.error("❌ المان‌های فرم پیدا نشدند");
        return;

    }

    buildCards(dom.platformSelect, dom.platformCards);

    if (dom.platformSelect.value) {

        updateContentType(dom.platformSelect.value);
        updateAdType(dom.platformSelect.value);

        if (CampaignData.PREV_CONTENT) {

            dom.contentTypeSelect.value = CampaignData.PREV_CONTENT;
            buildCards(dom.contentTypeSelect, dom.contentCards);

        }

        if (CampaignData.PREV_AD_TYPE) {

            dom.adTypeSelect.value = CampaignData.PREV_AD_TYPE;
            updateServiceTypes(CampaignData.PREV_AD_TYPE);
            buildCards(dom.adTypeSelect, dom.adCards);

        }

    }

    registerListeners();
    initDatepicker();

});
