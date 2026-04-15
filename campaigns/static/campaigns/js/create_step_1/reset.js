"use strict";

window.resetServiceType = function () {

    var dom = CampaignDOM;

    if (!dom.serviceSelect) return;

    dom.serviceSelect.innerHTML = '<option value="">انتخاب کنید...</option>';

    if (dom.serviceCards) dom.serviceCards.innerHTML = "";

    dom.serviceWrapper.style.display = "none";
    dom.minutesWrapper.style.display = "none";

    if (dom.minutesInput) dom.minutesInput.value = "";

};

window.resetAdType = function () {

    var dom = CampaignDOM;

    dom.adTypeSelect.innerHTML = '<option value="">انتخاب کنید...</option>';
    dom.adTypeSelect.disabled = true;

    if (dom.adCards) dom.adCards.innerHTML = "";

    dom.adHint.textContent = "ابتدا پلتفرم را انتخاب کنید";
    dom.adHint.style.display = "block";

    resetServiceType();

};

window.resetContentType = function () {

    var dom = CampaignDOM;

    dom.contentTypeSelect.innerHTML = '<option value="">انتخاب کنید...</option>';
    dom.contentTypeSelect.disabled = true;

    if (dom.contentCards) dom.contentCards.innerHTML = "";

    dom.contentHint.textContent = "ابتدا پلتفرم را انتخاب کنید";
    dom.contentHint.style.display = "block";

    resetAdType();

};
