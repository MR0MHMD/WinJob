"use strict";

window.registerListeners = function () {
    const dom = CampaignDOM;

    // لیسنر پلتفرم
    dom.platformSelect.addEventListener("change", function () {
        const platformId = this.value;

        if (platformId) {
            updateContentType(platformId);
            updateAdType(platformId);
            showAdType();
            hideContentType();
            hideServiceType();
            // ❌ حذف hideMinutes
            // hideMinutes();
            hideDateAndName();
        } else {
            hideAdType();
            hideContentType();
            resetContentType();
            hideServiceType();
            // ❌ حذف hideMinutes
            // hideMinutes();
            hideDateAndName();
        }

        if (window.CampaignDatepicker) {
            window.CampaignDatepicker.setStartMinDays(2);
        }
        validateForm();
    });

    // انتخاب نوع تبلیغ
    dom.adTypeSelect.addEventListener("change", function () {
        const adTypeId = this.value;

        if (adTypeId) {
            showContentType();
            if (window.toggleFreeCampaign) {
                window.toggleFreeCampaign();
            }
        } else {
            hideContentType();
        }

        hideServiceType();
        // ❌ حذف hideMinutes
        // hideMinutes();
        hideDateAndName();

        validateForm();
    });

    // انتخاب نوع محتوا
    dom.contentTypeSelect.addEventListener("change", function () {
        const selectedValue = this.value;
        const meta = CampaignData.CONTENT_TYPE_META[selectedValue];
        const slug = meta ? meta.slug : null;

        if (window.CampaignDatepicker) {
            window.CampaignDatepicker.setStartMinDays(slug === "content-production-team" ? 10 : 2);
        }

        if (slug === "content-production-team") {
            if (dom.adTypeSelect.value) {
                updateServiceTypes(dom.adTypeSelect.value);
                showServiceType();
            }
            // ❌ حذف hideMinutes
            // hideMinutes();
            hideDateAndName();
        } else {
            hideServiceType();
            // ❌ حذف hideMinutes
            // hideMinutes();
            showDateAndName();
        }

        validateForm();
    });

    // انتخاب خدمت تولید محتوا
    if (dom.serviceSelect) {
        dom.serviceSelect.addEventListener("change", function () {
            const selected = this.options[this.selectedIndex];
            if (!selected) return;

            // ❌ حذف منطق unit
            // var unit = selected.dataset.unit;
            // if (unit === "minute") {
            //     showMinutes();
            // } else {
            //     hideMinutes();
            // }

            // ========== نمایش واحدهای مجاز ==========
            const serviceId = this.value;
            const serviceInfo = document.getElementById("service-type-info");
            const unitsDisplay = document.getElementById("service-type-units-display");
            if (serviceInfo && unitsDisplay) {
                if (serviceId) {
                    const meta = CampaignData.SERVICE_TYPE_META[serviceId];
                    if (meta && meta.allowed_units_display) {
                        serviceInfo.style.display = "block";
                        unitsDisplay.textContent = "واحدهای مجاز: " + meta.allowed_units_display;
                    }
                } else {
                    serviceInfo.style.display = "none";
                }
            }

            showDateAndName();
        });
    }

    const nameInput = document.getElementById("id_name");
    // ❌ حذف minutesInput
    // var minutesInput = document.getElementById("id_minutes");
    if (nameInput) nameInput.addEventListener("input", validateForm);
    // if (minutesInput) minutesInput.addEventListener("input", validateForm);
};

if (CampaignDOM.freeCheckbox) {
    CampaignDOM.freeCheckbox.addEventListener('change', function () {
        window.toggleFreeCampaign();
        if (this.checked) {
            const selectedContent = CampaignDOM.contentTypeSelect.value;
            if (selectedContent) {
                const meta = CampaignData.CONTENT_TYPE_META[selectedContent];
                if (meta && meta.slug !== "ready-content") {
                    CampaignDOM.contentTypeSelect.value = "";
                    if (CampaignDOM.contentCards) {
                        CampaignDOM.contentCards.querySelectorAll('.option-card-inner').forEach(c => c.classList.remove('selected'));
                    }
                    window.hideServiceType();
                    // ❌ حذف hideMinutes
                    // window.hideMinutes();
                }
            }
        } else {
            const selectedContent = CampaignDOM.contentTypeSelect.value;
            if (selectedContent) {
                const meta = CampaignData.CONTENT_TYPE_META[selectedContent];
                if (meta && meta.slug === "content-production-team") {
                    if (CampaignDOM.adTypeSelect && CampaignDOM.adTypeSelect.value) {
                        window.updateServiceTypes(CampaignDOM.adTypeSelect.value);
                        window.showServiceType();
                    }
                } else {
                    window.hideServiceType();
                    // ❌ حذف hideMinutes
                    // window.hideMinutes();
                }
            }
        }
    });
}