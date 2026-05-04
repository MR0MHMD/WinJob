"use strict";

window.updateContentType = function (platformId) {

    var dom = CampaignDOM;

    resetContentType();

    if (!platformId) return;

    var choices = CampaignData.CONTENT_TYPES[String(platformId)];

    if (!choices || !choices.length) {

        dom.contentHint.textContent = "برای این پلتفرم نوع محتوایی تعریف نشده";
        return;

    }

    choices.forEach(function (item) {

        var opt = document.createElement("option");

        opt.value = item.id;
        opt.textContent = item.name;

        dom.contentTypeSelect.appendChild(opt);

    });

    dom.contentTypeSelect.disabled = false;
    dom.contentHint.style.display = "none";

    buildCards(dom.contentTypeSelect, dom.contentCards);

};

window.updateAdType = function (platformId) {

    var dom = CampaignDOM;

    resetAdType();

    if (!platformId) return;

    var choices = CampaignData.AD_TYPES[String(platformId)];

    if (!choices || !choices.length) {

        dom.adHint.textContent = "برای این پلتفرم نوع تبلیغی تعریف نشده";
        return;

    }

    choices.forEach(function (item) {

        var opt = document.createElement("option");

        opt.value = item.id;
        opt.textContent = item.name;

        dom.adTypeSelect.appendChild(opt);

    });

    dom.adTypeSelect.disabled = false;
    dom.adHint.style.display = "none";

    buildCards(dom.adTypeSelect, dom.adCards);

};

window.updateServiceTypes = function (adTypeId) {

    var dom = CampaignDOM;

    // گرفتن اسلاگ کانتنت تایپ انتخاب شده
    var selectedContentValue = dom.contentTypeSelect.value;
    var contentMeta = CampaignData.CONTENT_TYPE_META[selectedContentValue];
    var contentSlug = contentMeta ? contentMeta.slug : null;

    // فقط اگه اسلاگ برابر content-production-team باشه، سرویس‌ها لود بشن
    if (contentSlug !== "content-production-team") {
        resetServiceType();
        return;
    }

    resetServiceType();

    if (!adTypeId) return;

    var services = CampaignData.SERVICE_TYPES[String(adTypeId)];

    if (!services || !services.length) return;

    services.forEach(function (item) {

        var opt = document.createElement("option");

        opt.value = item.id;
        opt.textContent = item.name;
        opt.dataset.unit = item.unit;

        dom.serviceSelect.appendChild(opt);

    });

    dom.serviceWrapper.style.display = "block";

    buildCards(dom.serviceSelect, dom.serviceCards);

};
