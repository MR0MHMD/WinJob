"use strict";

window.registerListeners = function () {

    var dom = CampaignDOM;

    dom.platformSelect.addEventListener("change", function () {

        updateContentType(this.value);
        updateAdType(this.value);

    });

    dom.contentTypeSelect.addEventListener("change", function () {

        if (this.value === "1") {

            if (dom.adTypeSelect.value) {
                updateServiceTypes(dom.adTypeSelect.value);
            }

        } else {

            resetServiceType();

        }

    });

    dom.adTypeSelect.addEventListener("change", function () {

        updateServiceTypes(this.value);

    });

    if (dom.serviceSelect) {

        dom.serviceSelect.addEventListener("change", function () {

            var selected = this.options[this.selectedIndex];

            if (!selected) return;

            var unit = selected.dataset.unit;

            if (unit === "minute") {

                dom.minutesWrapper.style.display = "block";

            } else {

                dom.minutesWrapper.style.display = "none";

                if (dom.minutesInput) dom.minutesInput.value = "";

            }

        });

    }

};
