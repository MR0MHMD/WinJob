// campaigns/static/campaigns/js/step3_ready.js

const input = document.getElementById("id_media");
const zone = document.getElementById("uploadZone");
const placeholder = document.getElementById("uploadPlaceholder");
const previewWrapper = document.getElementById("uploadPreviewWrapper");

const previewImg = document.getElementById("uploadPreviewImage");
const previewVideo = document.getElementById("uploadPreviewVideo");

const removeBtn = document.getElementById("removeUploadBtn");

const progressBox = document.getElementById("uploadProgressBox");
const progressBar = document.getElementById("uploadProgressBar");
const fileName = document.getElementById("uploadFileName");
const uploadPercent = document.getElementById("uploadPercent");

const baleImage = document.getElementById("baleImage");
const baleVideo = document.getElementById("baleVideo");

const baleCaption = document.getElementById("baleCaption");
const baleLink = document.getElementById("baleLink");

// ---------- جدید: المان‌های فرم ----------
const submitBtn = document.querySelector("button[type='submit']");
const captionInput = document.getElementById("id_caption");
const linkInput = document.getElementById("id_link");
const utmEnabledCheckbox = document.getElementById("id_utm_enabled");
const utmFields = document.getElementById("utmFields");
const utmSource = document.getElementById("id_utm_source");
const utmMedium = document.getElementById("id_utm_medium");
const utmCampaign = document.getElementById("id_utm_campaign");
const utmContent = document.getElementById("id_utm_content");

// ---------- تابع چک کردن اعتبار فرم ----------
function validateForm() {
    let isValid = true;

    // چک کردن caption
    if (!captionInput.value.trim()) {
        isValid = false;
    }

    // چک کردن link
    const linkValue = linkInput.value.trim();
    if (!linkValue) {
        isValid = false;
    }
    // اگه لینک داره ولی با http شروع نشه
    if (linkValue && !linkValue.startsWith('http://') && !linkValue.startsWith('https://')) {
        isValid = false;
    }

    // اگه utm فعال باشه، فیلدهای اجباری رو چک کن
    if (utmEnabledCheckbox.checked) {
        if (!utmSource.value.trim()) isValid = false;
        if (!utmMedium.value.trim()) isValid = false;
        if (!utmCampaign.value.trim()) isValid = false;
        if (!utmContent.value.trim()) isValid = false;
    }

    // فعال/غیرفعال کردن دکمه
    if (isValid) {
        submitBtn.disabled = false;
        submitBtn.classList.remove("opacity-50");
    } else {
        submitBtn.disabled = true;
        submitBtn.classList.add("opacity-50");
    }
}

// ---------- تابع نمایش/مخفی کردن فیلدهای UTM ----------
function toggleUtmFields() {
    if (utmEnabledCheckbox.checked) {
        utmFields.classList.remove("d-none");
        // فیلدها رو required کن (سمت کلاینت)
        utmSource.required = true;
        utmMedium.required = true;
        utmCampaign.required = true;
        utmContent.required = true;
        document.getElementById("id_utm_term").required = false;
    } else {
        utmFields.classList.add("d-none");
        // required رو بردار
        utmSource.required = false;
        utmMedium.required = false;
        utmCampaign.required = false;
        utmContent.required = false;
    }
    validateForm();
}

// ---------- Event Listeners ----------
utmEnabledCheckbox.addEventListener("change", toggleUtmFields);
captionInput.addEventListener("input", validateForm);
linkInput.addEventListener("input", validateForm);
utmSource.addEventListener("input", validateForm);
utmMedium.addEventListener("input", validateForm);
utmCampaign.addEventListener("input", validateForm);
utmContent.addEventListener("input", validateForm);

// Helpers ---------------------------
function showPreview(file, url) {
    const type = file.type;
    fileName.textContent = file.name;
    placeholder.classList.add("d-none");
    previewWrapper.classList.remove("d-none");
    previewImg.classList.add("d-none");
    previewVideo.classList.add("d-none");
    baleImage.classList.add("d-none");
    baleVideo.classList.add("d-none");
    if (type.startsWith("image/")) {
        previewImg.src = url;
        previewImg.classList.remove("d-none");
        baleImage.src = url;
        baleImage.classList.remove("d-none");
    } else if (type.startsWith("video/")) {
        previewVideo.src = url;
        previewVideo.classList.remove("d-none");
        baleVideo.src = url;
        baleVideo.classList.remove("d-none");
    }
    validateForm();
}

function resetPreview() {
    input.value = "";
    previewImg.src = "";
    previewVideo.src = "";
    baleImage.src = "";
    baleVideo.src = "";
    previewImg.classList.add("d-none");
    previewVideo.classList.add("d-none");
    baleImage.classList.add("d-none");
    baleVideo.classList.add("d-none");
    previewWrapper.classList.add("d-none");
    placeholder.classList.remove("d-none");
    progressBox.classList.add("d-none");
    progressBar.style.width = "0%";
    fileName.textContent = "";
    uploadPercent.textContent = "";
    validateForm();
}

function simulateProgress(callback) {
    let p = 0;
    progressBox.classList.remove("d-none");
    const timer = setInterval(() => {
        p += 10 + (Math.random() * 10);
        if (p >= 100) p = 100;
        progressBar.style.width = p + "%";
        uploadPercent.textContent = p + "%";
        if (p === 100) {
            clearInterval(timer);
            setTimeout(() => progressBox.classList.add("d-none"), 400);
            callback();
        }
    }, 80);
}

// Events ---------------------------------
zone.addEventListener("click", () => input.click());
removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    resetPreview();
});
input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    simulateProgress(() => {
        showPreview(file, url);
    });
});

// Load existing media (edit mode)
document.addEventListener("DOMContentLoaded", () => {
    // تنظیم اولیه UTM fields
    toggleUtmFields();

    // Caption + Link preview
    baleCaption.textContent = captionInput.value.trim();
    const link = linkInput.value.trim();
    if (link) {
        baleLink.href = link;
        baleLink.textContent = link;
        baleLink.classList.remove("d-none");
    }

    // Existing media
    const existing = window.campaignData?.existingMedia || '';
    if (!existing) return;
    placeholder.classList.add("d-none");
    previewWrapper.classList.remove("d-none");
    const ext = existing.split('.').pop().toLowerCase();
    const videos = ["mp4", "webm", "ogg"];
    if (videos.includes(ext)) {
        previewVideo.src = existing;
        previewVideo.classList.remove("d-none");
        baleVideo.src = existing;
        baleVideo.classList.remove("d-none");
    } else {
        previewImg.src = existing;
        previewImg.classList.remove("d-none");
        baleImage.src = existing;
        baleImage.classList.remove("d-none");
    }
    validateForm();
});

// Caption + Link preview update
captionInput.addEventListener("input", () => {
    baleCaption.textContent = captionInput.value.trim();
    validateForm();
});
linkInput.addEventListener("input", () => {
    const link = linkInput.value.trim();
    if (link) {
        baleLink.href = link;
        baleLink.textContent = link;
        baleLink.classList.remove("d-none");
    } else {
        baleLink.classList.add("d-none");
    }
    validateForm();
});

// Disable submit button initially
submitBtn.disabled = true;
submitBtn.classList.add("opacity-50");