document.addEventListener('DOMContentLoaded', function () {
    const sendBtn = document.getElementById('send-reset-otp-btn');
    const phoneInput = document.querySelector('#forgot-password-form input[name="phone_number"]');
    const errorDiv = document.getElementById('forgot-error');

    if (!sendBtn || !phoneInput) return;

    sendBtn.addEventListener('click', async () => {
        const phoneNumber = phoneInput.value.trim();

        // پاک کردن خطای قبلی
        errorDiv.classList.add('d-none');
        errorDiv.innerHTML = '';

        if (!phoneNumber) {
            errorDiv.innerHTML = 'شماره تلفن را وارد کنید';
            errorDiv.classList.remove('d-none');
            return;
        }

        if (!/^09\d{9}$/.test(phoneNumber)) {
            errorDiv.innerHTML = 'شماره تلفن معتبر وارد کنید (مثل 09123456789)';
            errorDiv.classList.remove('d-none');
            return;
        }

        const originalText = sendBtn.innerHTML;
        sendBtn.disabled = true;
        sendBtn.innerHTML = 'در حال ارسال...';

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
                    type: 'reset_password'
                })
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = '/accounts/verify-otp/';
            } else {
                errorDiv.innerHTML = data.error || 'خطا در ارسال کد';
                errorDiv.classList.remove('d-none');
            }
        } catch (error) {
            console.error('Error:', error);
            errorDiv.innerHTML = 'مشکلی در ارتباط با سرور پیش آمد';
            errorDiv.classList.remove('d-none');
        } finally {
            sendBtn.disabled = false;
            sendBtn.innerHTML = originalText;
        }
    });

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
});