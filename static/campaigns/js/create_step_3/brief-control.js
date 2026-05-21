(function () {
    "use strict";

    // عناصر DOM
    const descriptionTextarea = document.getElementById("id_description");
    const charCountEl = document.getElementById("char-count");
    const minCharWarning = document.getElementById("min-char-warning");
    const submitBtn = document.getElementById("submit-btn");
    const briefSection = document.getElementById("brief-section");

    const goalSelect = document.getElementById("id_goal");
    const toneSelect = document.getElementById("id_tone");
    const brandInput = document.getElementById("id_brand_name");
    const goalDescription = document.getElementById("id_goal_description");
    const goalDescriptionWrapper = document.getElementById("goal-description-wrapper");

    const MIN_CHARS = 50;

    let isPlanSelected = false;
    let isAdContentValid = false;

    function getSelectedPlanId() {
        const planInput = document.querySelector('input[name="selected_plan"]');
        return planInput ? planInput.value : null;
    }

    function validateForm() {
        if (!submitBtn) return;

        const planValid = isPlanSelected && getSelectedPlanId() !== null && getSelectedPlanId() !== "";
        const adValid = isAdContentValid;
        const goalValid = goalSelect && goalSelect.value !== "";
        const toneValid = toneSelect && toneSelect.value !== "";
        const brandValid = brandInput && brandInput.value.trim().length > 0;
        const descValid = descriptionTextarea && descriptionTextarea.value.length >= MIN_CHARS;

        let goalDescValid = true;
        if (goalSelect && goalSelect.value === "other") {
            goalDescValid = goalDescription && goalDescription.value.trim().length > 0;
        }

        const isValid = planValid && adValid && goalValid && toneValid && brandValid && descValid && goalDescValid;
        submitBtn.disabled = !isValid;
    }

    function showBriefIfNeeded() {
        if (!briefSection) return;
        const shouldShow = isPlanSelected && isAdContentValid;
        if (shouldShow) {
            briefSection.style.display = "block";
            validateForm();
        } else {
            briefSection.style.display = "none";
        }
    }

    function updateAdContentStatus(event) {
        isAdContentValid = event.detail.adValid;
        isPlanSelected = event.detail.planSelected;
        showBriefIfNeeded();
        validateForm();
    }

    function attachBriefEvents() {
        if (descriptionTextarea) {
            descriptionTextarea.addEventListener("input", function () {
                updateCharCount();
                validateForm();
            });
        }
        if (goalSelect) {
            goalSelect.addEventListener("change", function () {
                toggleGoalDescription();
                validateForm();
            });
        }
        if (toneSelect) {
            toneSelect.addEventListener("change", validateForm);
        }
        if (brandInput) {
            brandInput.addEventListener("input", validateForm);
        }
        if (goalDescription) {
            goalDescription.addEventListener("input", validateForm);
        }
    }

    function updateCharCount() {
        if (!descriptionTextarea) return;
        const length = descriptionTextarea.value.length;
        charCountEl.textContent = toPersianNum(length);
        if (length < MIN_CHARS) {
            charCountEl.style.color = "#f97316";
            if (minCharWarning) minCharWarning.style.display = "block";
        } else {
            charCountEl.style.color = "#22c55e";
            if (minCharWarning) minCharWarning.style.display = "none";
        }
        validateForm();
    }

    function toggleGoalDescription() {
        if (!goalSelect || !goalDescriptionWrapper) return;
        goalDescriptionWrapper.style.display = goalSelect.value === "other" ? "block" : "none";
        validateForm();
    }

    function toPersianNum(num) {
        return String(num).replace(/\d/g, d => "۰۱۲۳۴۵۶۷۸۹"[d]);
    }

    window.initBriefControl = function () {
        if (briefSection) briefSection.style.display = "none";
        isPlanSelected = false;
        isAdContentValid = false;

        attachBriefEvents();
        toggleGoalDescription();
        updateCharCount();

        document.addEventListener("adContentChanged", updateAdContentStatus);

        document.addEventListener("planSelected", function () {
            isPlanSelected = true;
            showBriefIfNeeded();
            validateForm();
        });

        document.addEventListener("planCleared", function () {
            isPlanSelected = false;
            isAdContentValid = false;
            if (briefSection) briefSection.style.display = "none";
            validateForm();
        });

        validateForm();
    };
})();