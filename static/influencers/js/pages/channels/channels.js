(function () {
    'use strict';

    const modal = document.getElementById('channelModal');
    const modalTitle = document.getElementById('channelModalLabel');
    const form = document.getElementById('channelForm');
    const submitBtn = document.getElementById('modalSubmitBtn');
    const addBtn = document.getElementById('addChannelBtn');

    if (!modal || !form || !submitBtn) {
        return;
    }

    // =====================================================
    // فیلدهای اصلی فرم
    // =====================================================

    const platformField = form.querySelector(
        'select[name="platform"]'
    );

    const channelIdField = form.querySelector(
        'input[name="channel_id"]'
    );

    const channelNameField = form.querySelector(
        'input[name="channel_name"]'
    );

    const followersField = form.querySelector(
        'input[name="followers_count"]'
    );

    const provinceField = form.querySelector(
        'select[name="province"]'
    );

    const categoryField = form.querySelector(
        'select[name="category"]'
    );

    const urlField = form.querySelector(
        'input[name="url"]'
    );

    const avatarInput = form.querySelector(
        'input[type="file"][name="avatar"]'
    );

    const bioField = form.querySelector(
        'textarea[name="bio"]'
    );

    // =====================================================
    // عناصر انتخاب روش ثبت
    // =====================================================

    const registrationModeSection = document.getElementById(
        'channelRegistrationMode'
    );

    const channelDetailsSection = document.getElementById(
        'channelDetailsSection'
    );

    const quickRegistrationSection = document.getElementById(
        'quickRegistrationSection'
    );

    const manualRegistrationMode = document.getElementById(
        'manualRegistrationMode'
    );

    const quickRegistrationMode = document.getElementById(
        'quickRegistrationMode'
    );

    // =====================================================
    // عناصر بارگذاری سریع
    // =====================================================

    const quickChannelUrl = document.getElementById(
        'quickChannelUrl'
    );

    const quickImportButton = document.getElementById(
        'quickImportButton'
    );

    const quickImportFeedback = document.getElementById(
        'quickImportFeedback'
    );

    const leaveBaleBotAfterImport = document.getElementById(
        'leaveBaleBotAfterImport'
    );

    // =====================================================
    // پنل اتصال بازوی بله
    // =====================================================

    const baleBotConnectionPanel = document.getElementById(
        'baleBotConnectionPanel'
    );

    const baleBotUsername = document.getElementById(
        'baleBotUsername'
    );

    const openBaleBotButton = document.getElementById(
        'openBaleBotButton'
    );

    const copyBaleBotUsernameButton = document.getElementById(
        'copyBaleBotUsernameButton'
    );

    const retryBaleImportButton = document.getElementById(
        'retryBaleImportButton'
    );

    const baleBotCopyFeedback = document.getElementById(
        'baleBotCopyFeedback'
    );

    // =====================================================
    // عناصر تصویر
    // =====================================================

    const avatarPreviewImg = document.getElementById(
        'avatar-preview-img'
    );

    const avatarPlaceholder = document.getElementById(
        'avatar-placeholder'
    );

    const avatarRemoveBtn = document.getElementById(
        'avatar-remove-btn'
    );

    const avatarFileName = document.getElementById(
        'avatar-file-name'
    );

    const avatarWrapper = document.getElementById(
        'avatar-upload-wrapper'
    );

    // =====================================================
    // وضعیت داخلی
    // =====================================================

    const balePlatformId = String(
        form.dataset.balePlatformId || ''
    );

    const baleImportUrl =
        form.dataset.baleImportUrl ||
        '/influencers/api/channel-import/bale/';

    const hasServerErrors =
        form.dataset.hasErrors === 'true';

    let currentMode = hasServerErrors
        ? 'validation'
        : 'add';

    let currentChannelId = null;
    let quickImportCompleted = false;
    let quickImportInProgress = false;
    let currentBaleBotInfo = null;

    // =====================================================
    // فرمت اعداد
    // =====================================================

    const NumberFormatter = {
        cleanNumber(value) {
            return String(value || '')
                .replace(/,/g, '')
                .replace(/\D/g, '');
        },

        formatWithCommas(value) {
            const cleaned = this.cleanNumber(value);

            if (!cleaned) {
                return '';
            }

            return Number(cleaned).toLocaleString('en-US');
        },

        prepareForSubmit(value) {
            return this.cleanNumber(value);
        }
    };

    // =====================================================
    // ابزارهای عمومی
    // =====================================================

    function showElement(element) {
        element?.classList.remove('d-none');
    }

    function hideElement(element) {
        element?.classList.add('d-none');
    }

    function getCsrfToken() {
        const csrfInput = form.querySelector(
            'input[name="csrfmiddlewaretoken"]'
        );

        return csrfInput?.value || '';
    }

    function getCookie(name) {
        let cookieValue = null;

        if (!document.cookie) {
            return cookieValue;
        }

        const cookies = document.cookie.split(';');

        for (const rawCookie of cookies) {
            const cookie = rawCookie.trim();

            if (cookie.startsWith(`${name}=`)) {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );

                break;
            }
        }

        return cookieValue;
    }

    function updateBioCharCount() {
        const charCount = document.getElementById(
            'bioCharCount'
        );

        if (!bioField || !charCount) {
            return;
        }

        const length = bioField.value.length;

        charCount.textContent = String(length);

        if (length > 720) {
            charCount.style.color = '#dc3545';
        } else if (length > 500) {
            charCount.style.color = '#ffc107';
        } else {
            charCount.style.color = '#0ce110';
        }
    }

    // =====================================================
    // پیام‌های بارگذاری سریع
    // =====================================================

    function showQuickFeedback(type, message) {
        if (!quickImportFeedback) {
            return;
        }

        quickImportFeedback.className =
            `alert alert-${type} mt-3 mb-0`;

        quickImportFeedback.textContent = message;
    }

    function clearQuickFeedback() {
        if (!quickImportFeedback) {
            return;
        }

        quickImportFeedback.className =
            'alert d-none mt-3 mb-0';

        quickImportFeedback.textContent = '';
    }

    function setQuickImportLoading(isLoading) {
        quickImportInProgress = isLoading;

        if (quickImportButton) {
            if (isLoading) {
                quickImportButton.disabled = true;

                quickImportButton.innerHTML = `
                    <span
                        class="spinner-border spinner-border-sm me-1"
                        aria-hidden="true"
                    ></span>
                    در حال دریافت...
                `;
            } else {
                quickImportButton.textContent =
                    quickImportCompleted
                        ? 'دریافت مجدد'
                        : 'دریافت اطلاعات';
            }
        }

        if (retryBaleImportButton) {
            retryBaleImportButton.disabled = isLoading;

            retryBaleImportButton.innerHTML = isLoading
                ? `
                    <span
                        class="spinner-border spinner-border-sm me-1"
                        aria-hidden="true"
                    ></span>
                    در حال بررسی...
                `
                : `
                    <i class="fi-refresh-cw me-1"></i>
                    عضو کردم؛ بررسی مجدد
                `;
        }

        updateQuickImportButtonState();
    }

    function updateQuickImportButtonState() {
        if (!quickImportButton || !quickChannelUrl) {
            return;
        }

        const hasValue =
            quickChannelUrl.value.trim().length > 0;

        quickImportButton.disabled =
            quickImportInProgress || !hasValue;
    }

    // =====================================================
    // پنل اتصال بازو
    // =====================================================

    function hideBaleBotConnectionPanel() {
        currentBaleBotInfo = null;

        hideElement(baleBotConnectionPanel);
        hideElement(baleBotCopyFeedback);

        if (baleBotUsername) {
            baleBotUsername.textContent = '';
        }

        if (openBaleBotButton) {
            openBaleBotButton.href = '#';
        }
    }

    function showBaleBotConnectionPanel(botInfo) {
        currentBaleBotInfo = botInfo || null;

        const username = String(
            botInfo?.username || ''
        ).replace(/^@/, '');

        if (baleBotUsername) {
            baleBotUsername.textContent = username
                ? `@${username}`
                : 'آیدی بازو در دسترس نیست';
        }

        if (openBaleBotButton) {
            if (botInfo?.profile_url) {
                openBaleBotButton.href =
                    botInfo.profile_url;

                showElement(openBaleBotButton);
            } else {
                hideElement(openBaleBotButton);
            }
        }

        if (copyBaleBotUsernameButton) {
            copyBaleBotUsernameButton.disabled =
                !username;
        }

        hideElement(baleBotCopyFeedback);
        showElement(baleBotConnectionPanel);
    }

    async function copyText(text) {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return;
        }

        const textarea = document.createElement(
            'textarea'
        );

        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';

        document.body.appendChild(textarea);
        textarea.select();

        document.execCommand('copy');
        textarea.remove();
    }

    async function copyBaleBotUsername() {
        const username = String(
            currentBaleBotInfo?.username || ''
        ).replace(/^@/, '');

        if (!username) {
            return;
        }

        try {
            await copyText(`@${username}`);

            showElement(baleBotCopyFeedback);

            window.setTimeout(() => {
                hideElement(baleBotCopyFeedback);
            }, 2500);

        } catch (error) {
            showQuickFeedback(
                'danger',
                'کپی آیدی بازو انجام نشد. لطفاً آیدی را دستی کپی کنید.'
            );
        }
    }

    // =====================================================
    // مدیریت تصویر
    // =====================================================

    function clearAvatarPreview() {
        if (avatarInput) {
            avatarInput.value = '';
        }

        if (avatarPreviewImg) {
            avatarPreviewImg.src = '';
            avatarPreviewImg.style.display = 'none';
        }

        if (avatarPlaceholder) {
            avatarPlaceholder.style.display = 'flex';
        }

        if (avatarRemoveBtn) {
            avatarRemoveBtn.style.display = 'none';
        }

        if (avatarWrapper) {
            avatarWrapper.classList.remove('has-image');
        }

        if (avatarFileName) {
            avatarFileName.textContent = '';
        }
    }

    function showExistingAvatar(avatarUrl) {
        if (!avatarUrl || !avatarPreviewImg) {
            clearAvatarPreview();
            return;
        }

        if (avatarInput) {
            avatarInput.value = '';
        }

        avatarPreviewImg.src = avatarUrl;
        avatarPreviewImg.style.display = 'block';

        avatarPlaceholder?.style.setProperty(
            'display',
            'none'
        );

        avatarRemoveBtn?.style.setProperty(
            'display',
            'flex'
        );

        avatarWrapper?.classList.add('has-image');

        if (avatarFileName) {
            avatarFileName.textContent = 'تصویر فعلی';
        }
    }

    async function dataUrlToFile(
        dataUrl,
        filename,
        contentType
    ) {
        const response = await fetch(dataUrl);
        const blob = await response.blob();

        return new File(
            [blob],
            filename,
            {
                type: contentType ||
                    blob.type ||
                    'image/jpeg'
            }
        );
    }

    async function applyImportedAvatar(avatarData) {
        if (!avatarInput || !avatarData?.data_url) {
            clearAvatarPreview();
            return false;
        }

        try {
            const file = await dataUrlToFile(
                avatarData.data_url,
                avatarData.filename ||
                    'bale-channel-avatar.jpg',
                avatarData.content_type ||
                    'image/jpeg'
            );

            const dataTransfer = new DataTransfer();

            dataTransfer.items.add(file);
            avatarInput.files = dataTransfer.files;

            avatarInput.dispatchEvent(
                new Event('change', {
                    bubbles: true
                })
            );

            return true;

        } catch (error) {
            console.error(
                'Unable to apply imported avatar:',
                error
            );

            clearAvatarPreview();
            return false;
        }
    }

    // =====================================================
    // پاک‌سازی فرم
    // =====================================================

    function clearChannelDetails() {
        if (channelIdField) {
            channelIdField.value = '';
        }

        if (channelNameField) {
            channelNameField.value = '';
        }

        if (followersField) {
            followersField.value = '';
        }

        if (provinceField) {
            provinceField.value = '';
        }

        if (categoryField) {
            categoryField.value = '';
        }

        if (urlField) {
            urlField.value = '';
        }

        if (bioField) {
            bioField.value = '';
        }

        clearAvatarPreview();
        updateBioCharCount();
    }

    function resetQuickImportState({
        clearUrl = true
    } = {}) {
        quickImportCompleted = false;
        quickImportInProgress = false;

        if (clearUrl && quickChannelUrl) {
            quickChannelUrl.value = '';
        }

        if (leaveBaleBotAfterImport) {
            leaveBaleBotAfterImport.checked = true;
        }

        clearQuickFeedback();
        hideBaleBotConnectionPanel();

        if (quickImportButton) {
            quickImportButton.textContent =
                'دریافت اطلاعات';
        }

        updateQuickImportButtonState();
    }

    // =====================================================
    // جریان نمایش فرم
    // =====================================================

    function updateRegistrationFlow() {
        if (!platformField) {
            return;
        }

        const selectedPlatformId = String(
            platformField.value || ''
        );

        const isBalePlatform =
            balePlatformId !== '' &&
            selectedPlatformId === balePlatformId;

        const registrationMode = form.querySelector(
            'input[name="registration_mode"]:checked'
        )?.value || '';

        if (
            currentMode === 'edit' ||
            currentMode === 'validation'
        ) {
            hideElement(registrationModeSection);
            hideElement(quickRegistrationSection);
            showElement(channelDetailsSection);
            showElement(submitBtn);

            submitBtn.disabled = false;
            return;
        }

        if (!selectedPlatformId) {
            hideElement(registrationModeSection);
            hideElement(quickRegistrationSection);
            hideElement(channelDetailsSection);
            hideElement(submitBtn);
            return;
        }

        if (!isBalePlatform) {
            hideElement(registrationModeSection);
            hideElement(quickRegistrationSection);
            showElement(channelDetailsSection);
            showElement(submitBtn);

            submitBtn.disabled = false;
            return;
        }

        showElement(registrationModeSection);

        if (registrationMode === 'manual') {
            hideElement(quickRegistrationSection);
            showElement(channelDetailsSection);
            showElement(submitBtn);

            submitBtn.disabled = false;
            return;
        }

        if (registrationMode === 'quick') {
            showElement(quickRegistrationSection);

            if (quickImportCompleted) {
                showElement(channelDetailsSection);
                showElement(submitBtn);

                submitBtn.disabled = false;
            } else {
                hideElement(channelDetailsSection);
                hideElement(submitBtn);
            }

            updateQuickImportButtonState();
            return;
        }

        hideElement(quickRegistrationSection);
        hideElement(channelDetailsSection);
        hideElement(submitBtn);
    }

    // =====================================================
    // دریافت و تکمیل اطلاعات کانال
    // =====================================================

    async function populateImportedChannel(data) {
        if (channelIdField) {
            channelIdField.value =
                data.channel_id || '';
        }

        if (channelNameField) {
            channelNameField.value =
                data.channel_name || '';
        }

        if (followersField) {
            followersField.value =
                NumberFormatter.formatWithCommas(
                    data.followers_count
                );
        }

        if (urlField) {
            urlField.value = data.url || '';
        }

        if (bioField) {
            bioField.value = data.bio || '';
            updateBioCharCount();
        }

        return await applyImportedAvatar(
            data.avatar
        );
    }

    async function importBaleChannel() {
        if (!quickChannelUrl) {
            return;
        }

        const channelUrl =
            quickChannelUrl.value.trim();

        if (!channelUrl) {
            showQuickFeedback(
                'warning',
                'لینک کانال بله را وارد کنید.'
            );

            return;
        }

        setQuickImportLoading(true);
        hideBaleBotConnectionPanel();

        showQuickFeedback(
            'info',
            'در حال دریافت اطلاعات کانال از بله...'
        );

        try {
            const response = await fetch(
                baleImportUrl,
                {
                    method: 'POST',
                    credentials: 'same-origin',

                    headers: {
                        'Content-Type':
                            'application/json',

                        'X-CSRFToken':
                            getCsrfToken(),

                        'X-Requested-With':
                            'XMLHttpRequest'
                    },

                    body: JSON.stringify({
                        url: channelUrl,

                        leave_after_import: Boolean(
                            leaveBaleBotAfterImport
                                ?.checked
                        )
                    })
                }
            );

            let result;

            try {
                result = await response.json();
            } catch (error) {
                throw new Error(
                    'پاسخ نامعتبر از سرور دریافت شد.'
                );
            }

            if (!response.ok || !result.success) {
                throw new Error(
                    result.message ||
                    'دریافت اطلاعات کانال ناموفق بود.'
                );
            }

            const importedData = result.data || {};

            const avatarImported =
                await populateImportedChannel(
                    importedData
                );

            quickImportCompleted = true;
            updateRegistrationFlow();

            const warnings = Array.isArray(
                result.warnings
            )
                ? [...result.warnings]
                : [];

            if (
                importedData.avatar &&
                !avatarImported
            ) {
                warnings.push(
                    'تصویر دریافت شد، اما قرار دادن آن ' +
                    'داخل فرم انجام نشد.'
                );
            }

            const followersMissing =
                importedData.followers_count === null ||
                importedData.followers_count === undefined;

            if (
                importedData.requires_bot_membership ||
                followersMissing
            ) {
                showQuickFeedback(
                    'warning',
                    'اطلاعات پایه کانال دریافت شد، اما ' +
                    'برای دریافت تعداد دقیق اعضا باید ' +
                    'بازوی وینجاب را عضو عادی کانال کنید.'
                );

                showBaleBotConnectionPanel(
                    importedData.bot
                );

                return;
            }

            hideBaleBotConnectionPanel();

            if (warnings.length) {
                showQuickFeedback(
                    'warning',
                    [
                        'اطلاعات کانال دریافت شد.',
                        ...warnings
                    ].join('\n')
                );

                return;
            }

            if (importedData.bot_left_channel) {
                showQuickFeedback(
                    'success',
                    'اطلاعات کانال با موفقیت دریافت شد.\n' +
                    'بازوی وینجاب نیز طبق انتخاب شما ' +
                    'به‌صورت خودکار از کانال خارج شد.'
                );
            } else {
                showQuickFeedback(
                    'success',
                    'اطلاعات کانال با موفقیت دریافت شد. ' +
                    'لطفاً اطلاعات فرم را بررسی کنید.'
                );
            }

        } catch (error) {
            showQuickFeedback(
                'danger',
                error.message ||
                'هنگام دریافت اطلاعات کانال خطایی رخ داد.'
            );

        } finally {
            setQuickImportLoading(false);
        }
    }

    // =====================================================
    // ریست کامل فرم
    // =====================================================

    function resetForm() {
        form.reset();

        clearChannelDetails();
        resetQuickImportState();

        if (manualRegistrationMode) {
            manualRegistrationMode.checked = false;
        }

        if (quickRegistrationMode) {
            quickRegistrationMode.checked = false;
        }

        currentMode = 'add';
        currentChannelId = null;

        submitBtn.textContent = 'افزودن کانال';
        submitBtn.disabled = false;

        modalTitle.textContent =
            'افزودن کانال جدید';

        form.action = '';
        form.method = 'POST';

        form.querySelectorAll(
            'input[name="channel_id"]'
        ).forEach(element => {
            if (element.type === 'hidden') {
                element.remove();
            }
        });

        updateRegistrationFlow();
    }

    // =====================================================
    // ویرایش کانال
    // =====================================================

    function loadChannelDataFromButton(button) {
        const channelId = button.dataset.id;

        if (!channelId) {
            return;
        }

        platformField.value =
            button.dataset.platform || '';

        channelIdField.value =
            button.dataset.channelIdValue || '';

        channelNameField.value =
            button.dataset.name || '';

        followersField.value =
            NumberFormatter.formatWithCommas(
                button.dataset.followers || ''
            );

        if (provinceField) {
            provinceField.value =
                button.dataset.province || '';
        }

        if (categoryField) {
            categoryField.value =
                button.dataset.category || '';
        }

        urlField.value =
            button.dataset.url || '';

        if (bioField) {
            bioField.value =
                button.dataset.bio || '';

            updateBioCharCount();
        }

        showExistingAvatar(
            button.dataset.avatarUrl || ''
        );

        currentMode = 'edit';
        currentChannelId = channelId;

        submitBtn.textContent =
            'ذخیره تغییرات';

        modalTitle.textContent =
            'ویرایش کانال';

        form.action =
            `/influencers/my_channels/edit/${channelId}/`;

        form.method = 'POST';

        updateRegistrationFlow();
    }

    function editClickHandler(event) {
        event.preventDefault();
        event.stopPropagation();

        loadChannelDataFromButton(
            event.currentTarget
        );

        bootstrap.Modal
            .getOrCreateInstance(modal)
            .show();
    }

    function bindEditButtons() {
        document.querySelectorAll(
            '.edit-channel-btn'
        ).forEach(button => {
            button.removeEventListener(
                'click',
                editClickHandler
            );

            button.addEventListener(
                'click',
                editClickHandler
            );
        });
    }

    // =====================================================
    // حذف کانال
    // =====================================================

    function deleteClickHandler(event) {
        event.preventDefault();
        event.stopPropagation();

        const button = event.currentTarget;
        const channelId = button.dataset.id;

        if (!channelId) {
            return;
        }

        const overlay = document.getElementById(
            'confirm-overlay'
        );

        const channelNameElement =
            document.getElementById(
                'confirm-channel-name'
            );

        const confirmButton =
            document.getElementById(
                'confirm-delete'
            );

        const cancelButton =
            document.getElementById(
                'confirm-cancel'
            );

        if (
            !overlay ||
            !confirmButton ||
            !cancelButton
        ) {
            return;
        }

        if (channelNameElement) {
            channelNameElement.textContent =
                button.dataset.name || '';
        }

        overlay.classList.add('active');

        confirmButton.onclick = function () {
            const deleteForm =
                document.createElement('form');

            deleteForm.method = 'POST';

            deleteForm.action =
                `/influencers/my_channels/delete/${channelId}/`;

            const csrfInput =
                document.createElement('input');

            csrfInput.type = 'hidden';
            csrfInput.name =
                'csrfmiddlewaretoken';

            csrfInput.value =
                getCookie('csrftoken');

            deleteForm.appendChild(csrfInput);
            document.body.appendChild(deleteForm);

            deleteForm.submit();
        };

        cancelButton.onclick = function () {
            overlay.classList.remove('active');

            confirmButton.onclick = null;
            cancelButton.onclick = null;
        };
    }

    function bindDeleteButtons() {
        document.querySelectorAll(
            '.delete-btn'
        ).forEach(button => {
            button.removeEventListener(
                'click',
                deleteClickHandler
            );

            button.addEventListener(
                'click',
                deleteClickHandler
            );
        });
    }

    // =====================================================
    // فرمت تعداد اعضا
    // =====================================================

    function setupNumberFormatting() {
        if (!followersField) {
            return;
        }

        followersField.addEventListener(
            'input',
            function () {
                this.value =
                    NumberFormatter.formatWithCommas(
                        this.value
                    );
            }
        );

        followersField.addEventListener(
            'blur',
            function () {
                this.value =
                    NumberFormatter.formatWithCommas(
                        this.value
                    );
            }
        );

        followersField.value =
            NumberFormatter.formatWithCommas(
                followersField.value
            );
    }

    // =====================================================
    // رویدادها
    // =====================================================

    platformField?.addEventListener(
        'change',
        function () {
            if (
                currentMode === 'edit' ||
                currentMode === 'validation'
            ) {
                updateRegistrationFlow();
                return;
            }

            if (manualRegistrationMode) {
                manualRegistrationMode.checked = false;
            }

            if (quickRegistrationMode) {
                quickRegistrationMode.checked = false;
            }

            clearChannelDetails();
            resetQuickImportState();
            updateRegistrationFlow();
        }
    );

    manualRegistrationMode?.addEventListener(
        'change',
        updateRegistrationFlow
    );

    quickRegistrationMode?.addEventListener(
        'change',
        function () {
            updateRegistrationFlow();
            quickChannelUrl?.focus();
        }
    );

    quickChannelUrl?.addEventListener(
        'input',
        function () {
            if (quickImportCompleted) {
                quickImportCompleted = false;

                hideElement(channelDetailsSection);
                hideElement(submitBtn);
            }

            clearQuickFeedback();
            hideBaleBotConnectionPanel();
            updateQuickImportButtonState();
        }
    );

    quickChannelUrl?.addEventListener(
        'keydown',
        function (event) {
            if (
                event.key === 'Enter' &&
                !quickImportButton?.disabled
            ) {
                event.preventDefault();
                importBaleChannel();
            }
        }
    );

    quickImportButton?.addEventListener(
        'click',
        importBaleChannel
    );

    retryBaleImportButton?.addEventListener(
        'click',
        importBaleChannel
    );

    copyBaleBotUsernameButton?.addEventListener(
        'click',
        copyBaleBotUsername
    );

    bioField?.addEventListener(
        'input',
        updateBioCharCount
    );

    form.addEventListener(
        'submit',
        function () {
            if (followersField) {
                followersField.value =
                    NumberFormatter.prepareForSubmit(
                        followersField.value
                    );
            }

            submitBtn.disabled = true;
            submitBtn.textContent =
                'در حال ذخیره...';
        }
    );

    modal.addEventListener(
        'hidden.bs.modal',
        resetForm
    );

    modal.addEventListener(
        'shown.bs.modal',
        function () {
            updateBioCharCount();
            updateRegistrationFlow();
        }
    );

    addBtn?.addEventListener(
        'click',
        resetForm
    );

    // =====================================================
    // اتصال مجدد دکمه‌های کارت‌ها
    // =====================================================

    function rebindAll() {
        bindEditButtons();
        bindDeleteButtons();
    }

    const channelsContainer =
        document.getElementById(
            'channelsContainer'
        );

    if (channelsContainer) {
        const observer = new MutationObserver(
            function (mutations) {
                const changed = mutations.some(
                    mutation =>
                        mutation.addedNodes.length > 0
                );

                if (changed) {
                    rebindAll();
                }
            }
        );

        observer.observe(
            channelsContainer,
            {
                childList: true,
                subtree: true
            }
        );
    }

    // =====================================================
    // اجرای اولیه
    // =====================================================

    setupNumberFormatting();
    updateBioCharCount();
    updateQuickImportButtonState();
    updateRegistrationFlow();
    rebindAll();

})();