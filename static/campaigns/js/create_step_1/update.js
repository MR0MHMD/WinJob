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

// نمایش یا مخفی کردن بخش نوع تبلیغ
window.showAdType = function () {
    var dom = CampaignDOM;
    dom.adHint.style.display = "none";
    var adTypeSection = document.getElementById("ad-type-section");
    if (adTypeSection) adTypeSection.style.display = "block";
    validateForm();
};

window.hideAdType = function () {
    var adTypeSection = document.getElementById("ad-type-section");
    if (adTypeSection) adTypeSection.style.display = "none";
    resetAdType();
    validateForm();
};

window.showContentType = function () {
    var contentTypeSection = document.getElementById("content-type-section");
    if (contentTypeSection) contentTypeSection.style.display = "block";
    validateForm();
};

window.hideContentType = function () {
    var contentTypeSection = document.getElementById("content-type-section");
    if (contentTypeSection) contentTypeSection.style.display = "none";
    validateForm();
};

window.showServiceType = function () {
    var dom = CampaignDOM;
    if (dom.serviceWrapper) dom.serviceWrapper.style.display = "block";
    validateForm();
};

window.hideServiceType = function () {
    resetServiceType();
    validateForm();
};

window.showMinutes = function () {
    var dom = CampaignDOM;
    if (dom.minutesWrapper) dom.minutesWrapper.style.display = "block";
    validateForm();
};

window.hideMinutes = function () {
    var dom = CampaignDOM;
    if (dom.minutesWrapper) dom.minutesWrapper.style.display = "none";
    if (dom.minutesInput) dom.minutesInput.value = "";
    validateForm();
};

window.showDateAndName = function () {
    var dateSection = document.getElementById("date-section");
    var nameSection = document.getElementById("name-section");
    if (dateSection) dateSection.style.display = "block";
    if (nameSection) nameSection.style.display = "block";
    validateForm();
};

window.hideDateAndName = function () {
    var dateSection = document.getElementById("date-section");
    var nameSection = document.getElementById("name-section");
    if (dateSection) dateSection.style.display = "none";
    if (nameSection) nameSection.style.display = "none";
    validateForm();
};

// بررسی وضعیت فرم و فعال/غیرفعال کردن دکمه مرحله بعد
window.validateForm = function () {
    var dom = CampaignDOM;
    var submitBtn = document.querySelector('#step1-form button[type="submit"]');
    if (!submitBtn) return;

    var isValid = true;

    // پلتفرم همیشه نمایش داده می‌شود
    if (!dom.platformSelect.value) isValid = false;

    // نوع تبلیغ
    var adSection = document.getElementById("ad-type-section");
    if (adSection && adSection.style.display !== "none") {
        if (!dom.adTypeSelect.value) isValid = false;
    }

    // نوع محتوا
    var contentSection = document.getElementById("content-type-section");
    if (contentSection && contentSection.style.display !== "none") {
        if (!dom.contentTypeSelect.value) isValid = false;
    }

    // خدمات تولید محتوا
    if (dom.serviceWrapper && dom.serviceWrapper.style.display !== "none") {
        if (dom.serviceSelect && !dom.serviceSelect.value) isValid = false;
    }

    // مدت (دقیقه)
    if (dom.minutesWrapper && dom.minutesWrapper.style.display !== "none") {
        if (!dom.minutesInput || !dom.minutesInput.value.trim()) isValid = false;
    }

    // تاریخ (بازه زمانی)
    var dateSection = document.getElementById("date-section");
    if (dateSection && dateSection.style.display !== "none") {
        var startVal = document.getElementById("id_start_date").value;
        var endVal = document.getElementById("id_end_date").value;
        if (!startVal || !endVal) isValid = false;
    }

    // نام کمپین
    var nameSection = document.getElementById("name-section");
    var nameInput = document.getElementById("id_name");
    if (nameSection && nameSection.style.display !== "none") {
        if (!nameInput || !nameInput.value.trim()) isValid = false;
    }

    submitBtn.disabled = !isValid;
};
