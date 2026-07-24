// ==================== تأیید کانال ====================

let verificationInterval = null;

function openVerificationModal(channelId, channelName) {
    const modalEl = document.getElementById('verifyChannelModal');
    const modalBody = document.getElementById('verifyModalBody');
    const modal = new bootstrap.Modal(modalEl);

    modalBody.innerHTML = `
        <div class="py-5">
            <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;" role="status">
                <span class="visually-hidden">در حال بارگیری...</span>
            </div>
            <p class="text-muted mt-3">در حال آماده‌سازی...</p>
        </div>`;
    modal.show();

    fetch(`/influencers/channel/${channelId}/verify-modal/`, {
        headers: {'X-CSRFToken': getCookie('csrftoken')}
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'already_verified') {
            modalBody.innerHTML = `
                <div class="text-center py-4">
                    <i class="fi-check-circle text-success fs-1 mb-3 d-block"></i>
                    <div class="alert alert-success">${data.message}</div>
                    <button class="btn btn-outline-light rounded-pill" data-bs-dismiss="modal">بستن</button>
                </div>`;
            return;
        }
        if (data.status === 'error') {
            modalBody.innerHTML = `
                <div class="alert alert-danger">${data.message || 'خطا در دریافت اطلاعات'}</div>
                <button class="btn btn-secondary rounded-pill mt-3" data-bs-dismiss="modal">بستن</button>`;
            return;
        }
        if (data.status !== 'ok') {
            modalBody.innerHTML = `<div class="alert alert-danger">${data.message || 'خطا در دریافت اطلاعات'}</div>`;
            return;
        }

        modalBody.innerHTML = `
            <p class="text-muted mb-3">لطفاً کد زیر را در بیوگرافی کانال <strong class="text-primary">${escapeHtml(channelName)}</strong> قرار دهید.</p>
            <div class="bg-dark-2 p-3 rounded-3 mb-3 d-flex align-items-center justify-content-between" style="background: rgba(255,255,255,0.05);">
                <code class="fs-1 text-primary fw-bold" style="letter-spacing: 5px;" id="verificationCode">${data.code}</code>
                <button class="btn btn-outline-light rounded-pill" id="copyCodeBtn" onclick="copyToClipboard('verificationCode')">
                    <i class="fi-copy"></i> کپی
                </button>
            </div>
            <p class="text-muted small">سپس روی دکمه «بررسی کانال» کلیک کنید.</p>
            <button id="startVerifyBtn" class="btn btn-primary rounded-pill px-5 py-2 mt-2">بررسی کانال</button>
            <div id="verifyResult" class="mt-3"></div>
        `;

        document.getElementById('startVerifyBtn').onclick = () => {
            const btn = document.getElementById('startVerifyBtn');
            const resultDiv = document.getElementById('verifyResult');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> در حال بررسی...';
            resultDiv.innerHTML = '<div class="alert alert-info">درخواست ارسال شد، منتظر پاسخ...</div>';

            fetch(`/influencers/channel/${channelId}/start-verify/`, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')}
            })
            .then(res => res.json())
            .then(resData => {
                if (resData.status === 'pending') {
                    resultDiv.innerHTML = `<div class="alert alert-info">${resData.message}</div>`;
                    if (verificationInterval) clearInterval(verificationInterval);
                    verificationInterval = setInterval(() => {
                        fetch(`/influencers/channel/${channelId}/verification-status/`)
                            .then(r => r.json())
                            .then(statusData => {
                                if (statusData.status === 'approved') {
                                    clearInterval(verificationInterval);
                                    resultDiv.innerHTML = `<div class="alert alert-success">✅ کانال شما با موفقیت تأیید شد! صفحه در حال بازآوری...</div>`;
                                    setTimeout(() => location.reload(), 2000);
                                } else if (statusData.status === 'rejected') {
                                    clearInterval(verificationInterval);
                                    resultDiv.innerHTML = `<div class="alert alert-danger">❌ ${statusData.message}</div>`;
                                    btn.disabled = false;
                                    btn.innerHTML = 'بررسی کانال';
                                    setTimeout(() => location.reload(), 4000);
                                } else if (statusData.status === 'failed') {
                                    clearInterval(verificationInterval);
                                    resultDiv.innerHTML = `<div class="alert alert-warning">⚠️ ${statusData.message}</div>`;
                                    btn.disabled = false;
                                    btn.innerHTML = 'بررسی کانال';
                                }
                            }).catch(() => {});
                    }, 2500);
                } else if (resData.status === 'error') {
                    resultDiv.innerHTML = `<div class="alert alert-danger">${resData.message}</div>`;
                    btn.disabled = false;
                    btn.innerHTML = 'بررسی کانال';
                }
            })
            .catch(err => {
                resultDiv.innerHTML = '<div class="alert alert-danger">خطا در ارتباط با سرور</div>';
                btn.disabled = false;
                btn.innerHTML = 'بررسی کانال';
            });
        };
    })
    .catch(err => {
        modalBody.innerHTML = '<div class="alert alert-danger">خطا در ارتباط با سرور</div>';
    });
}

// راه‌اندازی دکمه تأیید کانال
const verifyBtn = document.getElementById('verifyChannelBtn');
if (verifyBtn) {
    verifyBtn.addEventListener('click', function (e) {
        e.preventDefault();
        openVerificationModal(
            parseInt(this.dataset.channelId || '{{ channel.id }}'),
            '{{ channel.channel_name|escapejs }}'
        );
    });
}