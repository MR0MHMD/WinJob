(function () {

    "use strict";

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

    function toPersianNum(num) {
        return String(num).replace(/\d/g, d => "۰۱۲۳۴۵۶۷۸۹"[d]);
    }

    function getSelectedTeam() {
        return document.querySelector('.team-radio:checked');
    }

    function updateCharCount() {

        if (!descriptionTextarea) return;

        const length = descriptionTextarea.value.length;

        charCountEl.textContent = toPersianNum(length);

        if (length < MIN_CHARS) {
            charCountEl.style.color = "#f97316";
            minCharWarning.style.display = "block";
        } else {
            charCountEl.style.color = "#22c55e";
            minCharWarning.style.display = "none";
        }

        validateForm();
    }

    function validateForm() {

        const teamSelected = !!getSelectedTeam();
        const goalValid = goalSelect && goalSelect.value !== "";
        const toneValid = toneSelect && toneSelect.value !== "";
        const brandValid = brandInput && brandInput.value.trim().length > 0;
        const descValid = descriptionTextarea && descriptionTextarea.value.length >= MIN_CHARS;

        let goalDescValid = true;

        if (goalSelect && goalSelect.value === "other") {
            goalDescValid = goalDescription && goalDescription.value.trim().length > 0;
        }

        const isValid =
            teamSelected &&
            goalValid &&
            toneValid &&
            brandValid &&
            descValid &&
            goalDescValid;

        submitBtn.disabled = !isValid;
    }

    function showBrief() {

        if (!briefSection) return;

        briefSection.style.display = "block";

        goalSelect?.focus();

        validateForm();
    }

    function hideBrief() {

        if (!briefSection) return;

        briefSection.style.display = "none";
    }

    function toggleGoalDescription() {

        if (!goalSelect || !goalDescriptionWrapper) return;

        goalDescriptionWrapper.style.display =
            goalSelect.value === "other" ? "block" : "none";

        validateForm();
    }

    window.initBriefControl = function () {

    hideBrief();

    document.addEventListener("teamSelected", () => {
        showBrief();
        validateForm();
    });

    descriptionTextarea?.addEventListener("input", updateCharCount);

    goalSelect?.addEventListener("change", toggleGoalDescription);
    toneSelect?.addEventListener("change", validateForm);
    brandInput?.addEventListener("input", validateForm);
    goalDescription?.addEventListener("input", validateForm);

    toggleGoalDescription();

    const selected = document.querySelector('.team-radio:checked');

    if (selected) {
        showBrief();
    }

    updateCharCount();

    validateForm();
};


})();
