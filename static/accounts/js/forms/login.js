const passwordSection = document.getElementById('password-login-section');
const otpSection = document.getElementById('otp-login-section');
const initialButtons = document.getElementById('initial-buttons');
const passwordModeBtnContainer = document.getElementById('password-mode-btn-container');
const otpModeBtn = document.getElementById('otp-mode-btn');
const passwordModeBtn = document.getElementById('password-mode-btn');

function switchToOtpMode() {
    passwordSection.style.display = 'none';
    otpSection.style.display = 'block';
    initialButtons.style.display = 'none';
    passwordModeBtnContainer.style.display = 'block';

    const errorDiv = document.getElementById('otp-error');
    errorDiv.classList.add('d-none');
    errorDiv.innerHTML = '';
}

function switchToPasswordMode() {
    passwordSection.style.display = 'block';
    otpSection.style.display = 'none';
    initialButtons.style.display = 'block';
    passwordModeBtnContainer.style.display = 'none';

    document.getElementById('otp-phone-input').value = '';

    const errorDiv = document.getElementById('otp-error');
    errorDiv.classList.add('d-none');
    errorDiv.innerHTML = '';
}

if (otpModeBtn) {
    otpModeBtn.addEventListener('click', switchToOtpMode);
}

if (passwordModeBtn) {
    passwordModeBtn.addEventListener('click', switchToPasswordMode);
}

const sendOtpBtn = document.getElementById('send-otp-submit');

if (sendOtpBtn) {
    sendOtpBtn.addEventListener('click', async () => {
        const phoneNumber = document.getElementById('otp-phone-input').value;

        if (!phoneNumber) {
            const errorDiv = document.getElementById('otp-error');
            errorDiv.innerHTML = 'شماره تلفن را وارد کنید';
            errorDiv.classList.remove('d-none');
            setTimeout(() => errorDiv.classList.add('d-none'), 5000);
            return;
        }

        const originalText = sendOtpBtn.innerHTML;
        sendOtpBtn.disabled = true;
        sendOtpBtn.innerHTML = 'در حال ارسال...';

        try {
            const response = await fetch('/accounts/api/request-otp/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    phone_number: phoneNumber,
                    type: 'login'
                })
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = '/accounts/verify-otp/';
            } else {
                const errorDiv = document.getElementById('otp-error');
                errorDiv.innerHTML = data.error || 'خطا در ارسال کد';
                errorDiv.classList.remove('d-none');
                setTimeout(() => errorDiv.classList.add('d-none'), 5000);
            }
        } catch (error) {
            console.error('Error:', error);
            const errorDiv = document.getElementById('otp-error');
            errorDiv.innerHTML = 'مشکلی در ارتباط با سرور پیش آمد';
            errorDiv.classList.remove('d-none');
            setTimeout(() => errorDiv.classList.add('d-none'), 5000);
        } finally {
            sendOtpBtn.disabled = false;
            sendOtpBtn.innerHTML = originalText;
        }
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function () {
    const hasError = document.querySelector('.alert-danger') !== null;
    if (hasError && otpSection.style.display !== 'none') {
        switchToPasswordMode();
    }
});