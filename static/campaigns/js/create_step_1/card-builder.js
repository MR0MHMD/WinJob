"use strict";

window.buildCards = function (select, container) {

    if (!container) return;

    container.innerHTML = "";

    Array.from(select.options).forEach(function (opt) {

        if (!opt.value) return;

        var meta = null;

        if (select.id === "id_platform") meta = CampaignData.PLATFORM_META[opt.value];
        if (select.id === "id_content_type") meta = CampaignData.CONTENT_TYPE_META[opt.value];
        if (select.id === "id_ad_type") meta = CampaignData.AD_TYPE_META[opt.value];
        if (select.id === "id_content_service_type") meta = CampaignData.SERVICE_TYPE_META[opt.value];

        var logo = meta ? meta.logo || "" : "";
        var icon = meta ? meta.icon || "" : "";
        var description = meta ? meta.description || "" : "";
        var unitLabel = meta ? meta.unit_label || "" : "";

        if (description && description.length > 120) {
            description = description.substring(0, 120) + "...";
        }

        var col = document.createElement("div");
        col.className = "col-md-4 option-card-wrapper";

        var selectedClass = select.value === opt.value ? "selected" : "";

        var logoHTML = logo
            ? `<div class="option-logo" style="text-align:center;margin-bottom:8px;">
                    <img src="${logo}" style="max-width:60px;max-height:60px;object-fit:contain;">
               </div>`
            : "";

        var iconHTML = icon
            ? `<div class="option-icon" style="text-align:center;margin-bottom:8px;font-size:22px;">
                    <i class="${icon} orange-icon"></i>
               </div>`
            : "";

        var descHTML = description
            ? `<div class="option-desc">${description}</div>`
            : "";

        var unitHTML = unitLabel
            ? `<div class="minute-warning">${unitLabel}</div>`
            : "";

        col.innerHTML = `
            <div class="option-card-inner ${selectedClass}" data-value="${opt.value}">
                <div class="check-badge">✓</div>
                ${logoHTML}
                ${iconHTML}
                <div class="option-title">${opt.textContent}</div>
                ${descHTML}
                ${unitHTML}
            </div>
        `;

        container.appendChild(col);

    });

    container.querySelectorAll(".option-card-inner").forEach(function (card) {

        card.addEventListener("click", function () {

            var value = this.dataset.value;

            select.value = value;

            select.dispatchEvent(new Event("change"));

            container.querySelectorAll(".option-card-inner").forEach(function (c) {
                c.classList.remove("selected");
            });

            this.classList.add("selected");

        });

    });

};
