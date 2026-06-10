"use strict";

window.registerListeners = function () {
    var dom = CampaignDOM;

    // در registerListeners، لیسنر پلتفرم:
    dom.platformSelect.addEventListener("change", function () {
        var platformId = this.value;

        if (platformId) {
            // ۱. بروزرسانی گزینه‌های نوع محتوا و نوع تبلیغ
            updateContentType(platformId);
            updateAdType(platformId);

            // ۲. نمایش نوع تبلیغ و مخفی کردن مراحل بعد
            showAdType();
            hideContentType();   // فقط مخفی می‌کنه، ریست نمی‌کنه
            hideServiceType();
            hideMinutes();
            hideDateAndName();
        } else {
            // اگر پلتفرم خالی شد، همه چیز رو ریست و مخفی کن
            hideAdType();
            hideContentType();
            // content type رو هم ریست کن چون پلتفرم نداریم
            resetContentType();
            hideServiceType();
            hideMinutes();
            hideDateAndName();
        }

        // ریست کردن آفست تاریخ پیش‌فرض
        if (window.CampaignDatepicker) {
            window.CampaignDatepicker.setStartMinDays(2);
        }
        validateForm();
    });

    // ۲. انتخاب نوع تبلیغ
    dom.adTypeSelect.addEventListener("change", function () {
        var adTypeId = this.value;

        if (adTypeId) {
            showContentType();
            if (window.toggleFreeCampaign) {
                window.toggleFreeCampaign();
            }
        } else {
            hideContentType();
        }

        // مخفی کردن مراحل بعدی
        hideServiceType();
        hideMinutes();
        hideDateAndName();

        validateForm();
    });

    // ۳. انتخاب نوع محتوا
    dom.contentTypeSelect.addEventListener("change", function () {
        var selectedValue = this.value;
        var meta = CampaignData.CONTENT_TYPE_META[selectedValue];
        var slug = meta ? meta.slug : null;

        // تنظیم محدودیت تاریخ
        if (window.CampaignDatepicker) {
            window.CampaignDatepicker.setStartMinDays(slug === "content-production-team" ? 10 : 2);
        }

        if (slug === "content-production-team") {
            // نمایش خدمات تولید محتوا
            if (dom.adTypeSelect.value) {
                updateServiceTypes(dom.adTypeSelect.value);
                showServiceType();
            }
            hideMinutes();
            hideDateAndName();
        } else {
            // محتوای آماده یا هر چیز دیگه
            hideServiceType();
            hideMinutes();
            showDateAndName();
        }

        validateForm();
    });

    // ۴. انتخاب خدمت تولید محتوا
    if (dom.serviceSelect) {
        dom.serviceSelect.addEventListener("change", function () {
            var selected = this.options[this.selectedIndex];
            if (!selected) return;
            var unit = selected.dataset.unit;

            if (unit === "minute") {
                showMinutes();
            } else {
                hideMinutes();
            }

            // حالا تاریخ و نام رو نشون بده
            showDateAndName();
        });
    }

    var nameInput = document.getElementById("id_name");
    var minutesInput = document.getElementById("id_minutes");
    if (nameInput) nameInput.addEventListener("input", validateForm);
    if (minutesInput) minutesInput.addEventListener("input", validateForm);
};

if (CampaignDOM.freeCheckbox) {
    CampaignDOM.freeCheckbox.addEventListener('change', function () {
        window.toggleFreeCampaign();
        // همچنین اگر نوع محتوا قبلاً انتخاب شده بود و اکنون غیرفعال شده، آن را ریست کن
        if (this.checked) {
            const selectedContent = CampaignDOM.contentTypeSelect.value;
            if (selectedContent) {
                const meta = CampaignData.CONTENT_TYPE_META[selectedContent];
                if (meta && meta.slug !== "ready-content") {
                    CampaignDOM.contentTypeSelect.value = "";
                    // حذف کلاس selected از کارت‌ها
                    if (CampaignDOM.contentCards) {
                        CampaignDOM.contentCards.querySelectorAll('.option-card-inner').forEach(c => c.classList.remove('selected'));
                    }
                    // مخفی کردن سرویس‌ها و دقیقه
                    window.hideServiceType();
                    window.hideMinutes();
                }
            }
        } else {
            // وقتی تیک برداشته شد، سرویس‌ها را دوباره بر اساس نوع محتوا نمایش بده
            const selectedContent = CampaignDOM.contentTypeSelect.value;
            if (selectedContent) {
                const meta = CampaignData.CONTENT_TYPE_META[selectedContent];
                if (meta && meta.slug === "content-production-team") {
                    // نمایش سرویس‌ها
                    if (CampaignDOM.adTypeSelect.value) {
                        window.updateServiceTypes(CampaignDOM.adTypeSelect.value);
                        window.showServiceType();
                    }
                } else {
                    window.hideServiceType();
                    window.hideMinutes();
                }
            }
        }
    });
}