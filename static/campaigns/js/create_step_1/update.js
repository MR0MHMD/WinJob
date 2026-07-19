"use strict";

window.updateContentType = function (platformId) {

    const dom = CampaignDOM;

    resetContentType();

    if (!platformId) return;

    const choices = CampaignData.CONTENT_TYPES[String(platformId)];

    if (!choices || !choices.length) {
        dom.contentHint.textContent = "برای این پلتفرم نوع محتوایی تعریف نشده";
        return;
    }

    choices.forEach(function (item) {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.name;
        dom.contentTypeSelect.appendChild(opt);
    });

    dom.contentTypeSelect.disabled = false;
    dom.contentHint.style.display = "none";

    buildCards(dom.contentTypeSelect, dom.contentCards);

    if (window.toggleFreeCampaign) {
        window.toggleFreeCampaign();
    }

};

window.updateAdType = function (platformId) {

    const dom = CampaignDOM;

    resetAdType();

    if (!platformId) return;

    const choices = CampaignData.AD_TYPES[String(platformId)];

    if (!choices || !choices.length) {
        dom.adHint.textContent = "برای این پلتفرم نوع تبلیغی تعریف نشده";
        return;
    }

    choices.forEach(function (item) {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.name;
        dom.adTypeSelect.appendChild(opt);
    });

    dom.adTypeSelect.disabled = false;
    dom.adHint.style.display = "none";

    buildCards(dom.adTypeSelect, dom.adCards);

};

window.updateServiceTypes = function (adTypeId) {

    const dom = CampaignDOM;

    const selectedContentValue = dom.contentTypeSelect.value;
    const contentMeta = CampaignData.CONTENT_TYPE_META[selectedContentValue];
    const contentSlug = contentMeta ? contentMeta.slug : null;

    if (contentSlug !== "content-production-team") {
        resetServiceType();
        return;
    }

    resetServiceType();

    if (!adTypeId) return;

    const services = CampaignData.SERVICE_TYPES[String(adTypeId)];

    if (!services || !services.length) return;

    services.forEach(function (item) {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.name;
        dom.serviceSelect.appendChild(opt);
    });

    dom.serviceWrapper.style.display = "block";

    buildCards(dom.serviceSelect, dom.serviceCards);

    // ========== نمایش واحدهای مجاز سرویس ==========
    const serviceInfo = document.getElementById("service-type-info");
    const unitsDisplay = document.getElementById("service-type-units-display");
    if (serviceInfo && unitsDisplay) {
        const selectedService = dom.serviceSelect.value;
        if (selectedService) {
            const meta = CampaignData.SERVICE_TYPE_META[selectedService];
            if (meta && meta.allowed_units_display) {
                serviceInfo.style.display = "block";
                unitsDisplay.textContent = "واحدهای مجاز: " + meta.allowed_units_display;
            }
        }
    }

};

// نمایش یا مخفی کردن بخش نوع تبلیغ
window.showAdType = function () {
    const dom = CampaignDOM;
    dom.adHint.style.display = "none";
    const adTypeSection = document.getElementById("ad-type-section");
    if (adTypeSection) adTypeSection.style.display = "block";
    validateForm();
};

window.hideAdType = function () {
    const adTypeSection = document.getElementById("ad-type-section");
    if (adTypeSection) adTypeSection.style.display = "none";
    resetAdType();
    validateForm();
};

window.showContentType = function () {
    const contentTypeSection = document.getElementById("content-type-section");
    if (contentTypeSection) contentTypeSection.style.display = "block";
    validateForm();
};

window.hideContentType = function () {
    const contentTypeSection = document.getElementById("content-type-section");
    if (contentTypeSection) contentTypeSection.style.display = "none";
    validateForm();
};

window.showServiceType = function () {
    const dom = CampaignDOM;
    if (dom.serviceWrapper) dom.serviceWrapper.style.display = "block";
    validateForm();
};

window.hideServiceType = function () {
    resetServiceType();
    validateForm();
};


window.showDateAndName = function () {
    const dateSection = document.getElementById("date-section");
    const nameSection = document.getElementById("name-section");
    if (dateSection) dateSection.style.display = "block";
    if (nameSection) nameSection.style.display = "block";
    validateForm();
};

window.hideDateAndName = function () {
    const dateSection = document.getElementById("date-section");
    const nameSection = document.getElementById("name-section");
    if (dateSection) dateSection.style.display = "none";
    if (nameSection) nameSection.style.display = "none";
    validateForm();
};

// بررسی وضعیت فرم و فعال/غیرفعال کردن دکمه مرحله بعد
window.validateForm = function () {
    const dom = CampaignDOM;
    const submitBtn = document.querySelector('#step1-form button[type="submit"]');
    if (!submitBtn) return;

    let isValid = true;

    // پلتفرم
    if (!dom.platformSelect.value) isValid = false;

    // نوع تبلیغ
    const adSection = document.getElementById("ad-type-section");
    if (adSection && adSection.style.display !== "none") {
        if (!dom.adTypeSelect.value) isValid = false;
    }

    // نوع محتوا
    const contentSection = document.getElementById("content-type-section");
    if (contentSection && contentSection.style.display !== "none") {
        if (!dom.contentTypeSelect.value) isValid = false;
    }

    // خدمات تولید محتوا (فقط اگه نمایش داده شده باشه)
    if (dom.serviceWrapper && dom.serviceWrapper.style.display !== "none") {
        if (dom.serviceSelect && !dom.serviceSelect.value) isValid = false;
    }


    // تاریخ
    const dateSection = document.getElementById("date-section");
    if (dateSection && dateSection.style.display !== "none") {
        const startVal = document.getElementById("id_start_date").value;
        const endVal = document.getElementById("id_end_date").value;
        if (!startVal || !endVal) isValid = false;
    }

    // نام کمپین
    const nameSection = document.getElementById("name-section");
    const nameInput = document.getElementById("id_name");
    if (nameSection && nameSection.style.display !== "none") {
        if (!nameInput || !nameInput.value.trim()) isValid = false;
    }

    const isFree = CampaignDOM.freeCheckbox && CampaignDOM.freeCheckbox.checked;

    if (!isFree) {
        if (dom.serviceWrapper && dom.serviceWrapper.style.display !== "none") {
            if (dom.serviceSelect && !dom.serviceSelect.value) isValid = false;
        }
    }

    submitBtn.disabled = !isValid;
};

// ============================================================
// تابع toggleFreeCampaign - اصلاح شده
// ============================================================
window.toggleFreeCampaign = function() {
    const isFree = CampaignDOM.freeCheckbox && CampaignDOM.freeCheckbox.checked;
    const contentTypeSelect = CampaignDOM.contentTypeSelect;
    const contentTypeCards = CampaignDOM.contentCards;

    if (!contentTypeSelect) return;

    if (isFree) {
        Array.from(contentTypeSelect.options).forEach(opt => {
            const optionValue = opt.value;
            if (optionValue) {
                const meta = CampaignData.CONTENT_TYPE_META[optionValue];
                const isReady = meta && meta.slug === "ready-content";
                opt.disabled = !isReady;
                if (contentTypeCards) {
                    const card = contentTypeCards.querySelector(`.option-card-inner[data-value="${optionValue}"]`);
                    if (card) {
                        if (!isReady) {
                            card.style.opacity = '0.5';
                            card.style.pointerEvents = 'none';
                            card.classList.add('disabled-card');
                        } else {
                            card.style.opacity = '';
                            card.style.pointerEvents = '';
                            card.classList.remove('disabled-card');
                        }
                    }
                }
            }
        });
        if (contentTypeSelect.value) {
            const selectedMeta = CampaignData.CONTENT_TYPE_META[contentTypeSelect.value];
            if (selectedMeta && selectedMeta.slug !== "ready-content") {
                contentTypeSelect.value = "";
                if (contentTypeCards) {
                    contentTypeCards.querySelectorAll('.option-card-inner').forEach(c => c.classList.remove('selected'));
                }
                window.hideServiceType();
            }
        } else {
            window.hideServiceType();
        }
        if (CampaignDOM.contentHint) {
            CampaignDOM.contentHint.textContent = "در حالت رایگان فقط «محتوای آماده» قابل انتخاب است.";
        }
    } else {
        Array.from(contentTypeSelect.options).forEach(opt => {
            opt.disabled = false;
        });
        if (contentTypeCards) {
            contentTypeCards.querySelectorAll('.option-card-inner').forEach(card => {
                card.style.opacity = '';
                card.style.pointerEvents = '';
                card.classList.remove('disabled-card');
            });
        }
        if (CampaignDOM.contentHint) {
            CampaignDOM.contentHint.textContent = "ابتدا نوع تبلیغ را انتخاب کنید";
        }
        const selectedContent = contentTypeSelect.value;
        if (selectedContent) {
            const meta = CampaignData.CONTENT_TYPE_META[selectedContent];
            if (meta && meta.slug === "content-production-team") {
                if (CampaignDOM.adTypeSelect && CampaignDOM.adTypeSelect.value) {
                    window.updateServiceTypes(CampaignDOM.adTypeSelect.value);
                    window.showServiceType();
                }
            } else {
                window.hideServiceType();
            }
        }
    }
    validateForm();
};