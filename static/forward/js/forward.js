/**
 * اسکریپت‌های تعاملی اختصاصی پنل وین فوروارد (forward.js)
 * شامل:
 * ۱. محاسبه زنده مبلغ اشتراک در صفحه پلن‌ها و بخش ارتقای روزشمار (با حذف کامل ویرگول/جداکننده هزارگان قبل از parseInt)
 * ۲. انتخابگر تعاملی روش پرداخت (درگاه زرین‌پال / کیف پول) در صفحه پیش‌فاکتور
 * ۳. کپی سریع دستورات و لینک‌ها با بازخورد بصری
 * ۴. استودیو ارسال پیام: تب‌های نوع محتوا، پیش‌نمایش زنده موبایل، شمارنده کاراکتر و انتخاب همه کانال‌ها
 */

document.addEventListener("DOMContentLoaded", function () {
    /**
     * تبدیل امن رشته عددی (حتی دارای ویرگول هزارگان یا ارقام فارسی/عربی) به عدد صحیح.
     */
    function parseCleanInt(rawVal) {
        if (rawVal === null || rawVal === undefined) return 0;
        let str = String(rawVal);
        const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
        const arabicDigits = "٠١٢٣٤٥٦٧٨٩";
        for (let i = 0; i < 10; i++) {
            str = str.replace(new RegExp(persianDigits[i], "g"), String(i));
            str = str.replace(new RegExp(arabicDigits[i], "g"), String(i));
        }
        str = str.replace(/[^0-9]/g, "");
        return parseInt(str || "0", 10) || 0;
    }

    /* ── ۱. محاسبه زنده مبلغ پلن‌های اشتراک (plans.html) ── */
    document.querySelectorAll(".wf-plan-form").forEach(function (form) {
        const unitPrice = parseCleanInt(form.dataset.unitPrice);
        const totalEl = form.querySelector(".wf-total-price");
        const countEl = form.querySelector(".wf-selected-count");
        const checkboxes = form.querySelectorAll(".wf-platform-cb");

        function updatePlanPrice() {
            let count = 0;
            checkboxes.forEach(function (cb) {
                const tile = cb.closest(".wf-platform-option-tile");
                if (cb.checked) {
                    count++;
                    if (tile) tile.classList.add("is-checked");
                } else {
                    if (tile) tile.classList.remove("is-checked");
                }
            });
            if (totalEl) {
                totalEl.textContent = (count * unitPrice).toLocaleString("en-US");
            }
            if (countEl) {
                countEl.textContent = count;
            }
        }

        checkboxes.forEach(function (cb) {
            cb.addEventListener("change", updatePlanPrice);
        });
        updatePlanPrice();
    });

    /* ── ۲. محاسبه زنده هزینه افزودن پلتفرم در میانه دوره (plans.html) ── */
    const proratedForm = document.getElementById("wfProratedForm");
    if (proratedForm) {
        const proratedUnit = parseCleanInt(proratedForm.dataset.proratedUnit);
        const proratedTotalEl = document.getElementById("wfProratedTotal");
        const proratedBtn = document.getElementById("wfProratedSubmit");
        const proratedCbs = proratedForm.querySelectorAll(".wf-prorated-cb");

        function updateProrated() {
            let selected = 0;
            proratedCbs.forEach(function (cb) {
                const tile = cb.closest(".wf-platform-option-tile");
                if (cb.checked) {
                    selected++;
                    if (tile) tile.classList.add("is-checked");
                } else {
                    if (tile) tile.classList.remove("is-checked");
                }
            });
            if (proratedTotalEl) {
                proratedTotalEl.textContent = (selected * proratedUnit).toLocaleString("en-US");
            }
            if (proratedBtn) {
                proratedBtn.disabled = selected === 0;
            }
        }

        proratedCbs.forEach(function (cb) {
            cb.addEventListener("change", updateProrated);
        });
        updateProrated();
    }

    /* ── ۳. انتخابگر تعاملی روش پرداخت در صفحه پیش‌فاکتور (order_detail.html) ── */
    const paymentCards = document.querySelectorAll(".wf-payment-method-card[data-pay-target]");
    const payOrderForm = document.getElementById("wfOrderPayForm");
    if (paymentCards.length > 0 && payOrderForm) {
        paymentCards.forEach(function (card) {
            card.addEventListener("click", function () {
                if (card.classList.contains("is-disabled")) return;
                paymentCards.forEach(function (c) { c.classList.remove("is-selected"); });
                card.classList.add("is-selected");
                const targetUrl = card.getAttribute("data-pay-url");
                if (targetUrl) {
                    payOrderForm.setAttribute("action", targetUrl);
                }
            });
        });
    }

    /* ── ۴. دکمه‌های کپی در کلیپ‌بورد ── */
    document.querySelectorAll("[data-wf-copy]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const text = btn.getAttribute("data-wf-copy") || "";
            if (!text) return;
            navigator.clipboard.writeText(text).then(function () {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check2-all"></i> کپی شد!';
                setTimeout(function () {
                    btn.innerHTML = originalHtml;
                }, 1800);
            });
        });
    });

    /* ── ۵. استودیو ارسال پیام همگانی (send.html) ── */
    const contentTypeSelect = document.getElementById("id_content_type");
    const typePillBtns = document.querySelectorAll(".wf-type-pill-btn[data-content-type]");
    const fileSection = document.getElementById("file-upload-section");
    const textInput = document.getElementById("id_text");
    const previewText = document.getElementById("wfPreviewText");
    const previewMediaBadge = document.getElementById("wfPreviewMediaBadge");
    const charCounter = document.getElementById("wfCharCounter");
    const fileInput = document.getElementById("id_file");
    const fileNameDisplay = document.getElementById("wfFileNameDisplay");

    function updateStudioState() {
        if (!contentTypeSelect) return;
        const val = contentTypeSelect.value;

        typePillBtns.forEach(function (btn) {
            if (btn.getAttribute("data-content-type") === val) {
                btn.classList.add("is-active");
            } else {
                btn.classList.remove("is-active");
            }
        });

        if (fileSection) {
            fileSection.style.display = val === "text" ? "none" : "block";
        }
        if (previewMediaBadge) {
            if (val === "text") {
                previewMediaBadge.style.display = "none";
            } else {
                previewMediaBadge.style.display = "block";
                const labels = {
                    photo: "🖼️ پیوست تصویر",
                    video: "🎬 پیوست ویدیو",
                    audio: "🎵 پیوست فایل صوتی",
                    document: "📎 پیوست سند/فایل",
                };
                previewMediaBadge.textContent = labels[val] || "📎 فایل رسانه";
            }
        }
    }

    if (contentTypeSelect) {
        contentTypeSelect.addEventListener("change", updateStudioState);
        typePillBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                contentTypeSelect.value = btn.getAttribute("data-content-type");
                updateStudioState();
            });
        });
        updateStudioState();
    }

    if (textInput) {
        function syncTextPreview() {
            const val = textInput.value || "";
            if (previewText) {
                previewText.textContent = val.trim() ? val : "متن یا کپشن پیام شما به صورت زنده در این حباب نمایش داده می‌شود...";
            }
            if (charCounter) {
                charCounter.textContent = val.length.toLocaleString("en-US") + " / 4,096 کاراکتر";
            }
        }
        textInput.addEventListener("input", syncTextPreview);
        syncTextPreview();
    }

    if (fileInput && fileNameDisplay) {
        fileInput.addEventListener("change", function () {
            if (fileInput.files && fileInput.files.length > 0) {
                fileNameDisplay.textContent = "✅ فایل انتخاب‌شده: " + fileInput.files[0].name;
                fileNameDisplay.style.display = "block";
            } else {
                fileNameDisplay.style.display = "none";
            }
        });
    }

    /* انتخاب کارت‌های کانال در استودیو ارسال */
    const channelCheckboxes = document.querySelectorAll(".wf-channel-cb");
    channelCheckboxes.forEach(function (cb) {
        function syncTile() {
            const tile = cb.closest(".wf-channel-tile");
            if (!tile) return;
            if (cb.checked && !cb.disabled) {
                tile.classList.add("is-selected");
            } else {
                tile.classList.remove("is-selected");
            }
        }
        cb.addEventListener("change", syncTile);
        syncTile();
    });

    const selectAllBtn = document.getElementById("wfSelectAllChannels");
    if (selectAllBtn) {
        selectAllBtn.addEventListener("click", function () {
            const enabledCbs = Array.from(channelCheckboxes).filter(function (cb) { return !cb.disabled; });
            const allChecked = enabledCbs.every(function (cb) { return cb.checked; });
            enabledCbs.forEach(function (cb) {
                cb.checked = !allChecked;
                cb.dispatchEvent(new Event("change"));
            });
            selectAllBtn.innerHTML = allChecked
                ? '<i class="bi bi-check2-all"></i> انتخاب همه کانال‌های مجاز'
                : '<i class="bi bi-x-lg"></i> لغو انتخاب همه';
        });
    }
});

/* ── مودال تایید اختصاصی وین‌فوروارد (جایگزین کامل window.confirm) ── */
document.addEventListener("DOMContentLoaded", function () {
    const modalEl = document.getElementById("wfGlobalConfirmModal");
    if (!modalEl) return;
    const titleEl = document.getElementById("wfConfirmModalTitle");
    const bodyEl = document.getElementById("wfConfirmModalBody");
    const submitBtn = document.getElementById("wfConfirmModalSubmit");
    let pendingForm = null;

    document.addEventListener("submit", function (e) {
        const form = e.target;
        if (!form || !form.matches("form[data-wf-confirm]")) return;
        if (form.dataset.wfConfirmed === "1") return;

        e.preventDefault();
        pendingForm = form;
        if (titleEl) titleEl.textContent = form.dataset.wfConfirmTitle || "تایید حذف یا تغییر";
        if (bodyEl) bodyEl.textContent = form.dataset.wfConfirm || "آیا از انجام این عملیات اطمینان دارید؟";
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="bi bi-check2-circle"></i> ' + (form.dataset.wfConfirmBtn || "بله، انجام شود");
        }
        if (window.bootstrap && window.bootstrap.Modal) {
            window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
    });

    if (submitBtn) {
        submitBtn.addEventListener("click", function () {
            if (!pendingForm) return;
            pendingForm.dataset.wfConfirmed = "1";
            if (window.bootstrap && window.bootstrap.Modal) {
                window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
            }
            pendingForm.submit();
            pendingForm = null;
        });
    }
});
