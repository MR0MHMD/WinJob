(function() {
    'use strict';

    function init() {
        const adContentSection = document.getElementById('ad-content-section');
        const adCaptionInput = document.getElementById('id_ad_caption');
        const adLinkInput = document.getElementById('id_ad_link');
        const adCaptionCounter = document.getElementById('ad-caption-counter');
        const adLinkCounter = document.getElementById('ad-link-counter');
        const linkPreview = document.getElementById('link-preview');
        const linkPreviewText = document.getElementById('link-preview-text');
        const briefSection = document.getElementById('brief-section');
        const goalSelect = document.getElementById('id_goal');

        if (!adCaptionInput || !adLinkInput) {
            console.warn('ادیتور: فیلدهای متن تبلیغ یا لینک یافت نشد');
            return;
        }

        let isPlanSelected = false;

        // اعتبارسنجی محتوای تبلیغ
        function validateAdContent() {
            const caption = adCaptionInput.value.trim() || '';
            const link = adLinkInput.value.trim() || '';
            const captionValid = caption.length >= 10;
            const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
            const linkValid = link !== '' && urlPattern.test(link);
            return captionValid && linkValid;
        }

        // به‌روزرسانی وضعیت و ارسال رویداد
        function updateSubmitButtonState() {
            const adValid = validateAdContent();
            document.dispatchEvent(new CustomEvent('adContentChanged', {
                detail: { adValid, planSelected: isPlanSelected }
            }));
        }

        // نمایش بخش محتوای تبلیغ و اسکرول به فیلد متن
        function showAdContentAndScroll() {
            if (adContentSection && adContentSection.style.display !== 'block') {
                adContentSection.style.display = 'block';
                adCaptionInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                adCaptionInput.focus();
            }
        }

        // نمایش بریف در صورت نیاز (اسکرول به هدف محتوا)
        function showBriefIfNeeded() {
            if (!briefSection) return;
            const shouldShow = isPlanSelected && validateAdContent();
            if (shouldShow) {
                if (briefSection.style.display !== 'block') {
                    briefSection.style.display = 'block';
                    if (goalSelect) {
                        goalSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        goalSelect.focus();
                    }
                }
            } else {
                if (briefSection.style.display === 'block') {
                    briefSection.style.display = 'none';
                }
            }
        }

        // شمارش کاراکتر متن تبلیغ
        function updateAdCaptionCounter() {
            const length = adCaptionInput.value.length;
            if (adCaptionCounter) {
                adCaptionCounter.textContent = `${length} / حداقل ۱۰ کاراکتر`;
                if (length >= 10) {
                    adCaptionCounter.classList.add('valid');
                    adCaptionCounter.classList.remove('invalid');
                } else {
                    adCaptionCounter.classList.add('invalid');
                    adCaptionCounter.classList.remove('valid');
                }
            }
        }

        // اعتبارسنجی لینک و نمایش پیش‌نمایش
        function validateLink() {
            const link = adLinkInput.value.trim();
            if (!adLinkCounter) return false;
            if (link === '') {
                adLinkCounter.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> لینک الزامی است';
                adLinkCounter.classList.add('invalid');
                adLinkCounter.classList.remove('valid');
                if (linkPreview) linkPreview.classList.add('d-none');
                return false;
            }
            const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
            if (urlPattern.test(link)) {
                adLinkCounter.innerHTML = '<i class="bi bi-check-circle-fill"></i> معتبر';
                adLinkCounter.classList.add('valid');
                adLinkCounter.classList.remove('invalid');
                if (linkPreview && linkPreviewText) {
                    let displayLink = link;
                    if (!link.startsWith('http')) displayLink = 'https://' + link;
                    linkPreviewText.textContent = displayLink;
                    linkPreview.classList.remove('d-none');
                }
                return true;
            } else {
                adLinkCounter.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> لینک نامعتبر است';
                adLinkCounter.classList.add('invalid');
                adLinkCounter.classList.remove('valid');
                if (linkPreview) linkPreview.classList.add('d-none');
                return false;
            }
        }

        function attachEvents() {
            adCaptionInput.addEventListener('input', function() {
                updateAdCaptionCounter();
                showBriefIfNeeded();
                updateSubmitButtonState();
            });
            adLinkInput.addEventListener('input', function() {
                validateLink();
                showBriefIfNeeded();
                updateSubmitButtonState();
            });
            adLinkInput.addEventListener('blur', function() {
                validateLink();
                showBriefIfNeeded();
                updateSubmitButtonState();
            });
        }

        // گوش دادن به رویدادهای انتخاب پلن
        document.addEventListener('planSelected', function() {
            isPlanSelected = true;
            showAdContentAndScroll();
            showBriefIfNeeded();
            updateSubmitButtonState();
        });

        document.addEventListener('planCleared', function() {
            isPlanSelected = false;
            if (adContentSection) adContentSection.style.display = 'none';
            if (briefSection) briefSection.style.display = 'none';
            updateSubmitButtonState();
        });

        // مقداردهی اولیه
        if (adContentSection) adContentSection.style.display = 'none';
        if (briefSection) briefSection.style.display = 'none';
        attachEvents();
        updateAdCaptionCounter();
        validateLink();

        // در صورت وجود پلن انتخاب شده (حالت ویرایش)
        const existingPlan = document.querySelector('input[name="selected_plan"]');
        if (existingPlan && existingPlan.value) {
            isPlanSelected = true;
            showAdContentAndScroll();
            showBriefIfNeeded();
            updateSubmitButtonState();
        }

        // اعتبارسنجی نهایی فرم قبل از ارسال
        const form = document.getElementById('step3-form');
        if (form) {
            form.addEventListener('submit', function(e) {
                const adCaption = adCaptionInput.value.trim() || '';
                const adLink = adLinkInput.value.trim() || '';
                let hasError = false;
                if (adCaption.length < 10) {
                    alert('❌ متن تبلیغ باید حداقل ۱۰ کاراکتر باشد.');
                    adCaptionInput.focus();
                    hasError = true;
                }
                if (adLink === '') {
                    alert('❌ لینک مقصد الزامی است. برای رهگیری کلیک‌ها نیاز داریم.');
                    adLinkInput.focus();
                    hasError = true;
                } else {
                    const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
                    if (!urlPattern.test(adLink)) {
                        alert('❌ لینک مقصد معتبر نیست. لطفاً یک آدرس صحیح وارد کنید.');
                        adLinkInput.focus();
                        hasError = true;
                    }
                }
                if (hasError) e.preventDefault();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();