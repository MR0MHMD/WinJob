document.addEventListener('DOMContentLoaded', function () {
    const saveBtn = document.getElementById('save-password-btn');
    const passwordInput = document.querySelector('#reset-password-form input[name="password"]');
    const confirmInput = document.querySelector('#reset-password-form input[name="password_confirm"]');
    const errorDiv = document.getElementById('reset-error');

    if (!saveBtn || !passwordInput || !confirmInput) return;

    saveBtn.addEventListener('click', async () => {
        const password = passwordInput.value;
        const confirm = confirmInput.value;

        errorDiv.classList.add('d-none');
        errorDiv.innerHTML = '';

        if (!password || !confirm) {
            errorDiv.innerHTML = 'رمز عبور و تکرار آن را وارد کنید';
            errorDiv.classList.remove('d-none');
            return;
        }

        if (password !== confirm) {
            errorDiv.innerHTML = 'رمز عبور و تکرار آن یکسان نیست';
            errorDiv.classList.remove('d-none');
            return;
        }

        if (password.length < 8) {
            errorDiv.innerHTML = 'رمز عبور باید حداقل ۸ کاراکتر باشد';
            errorDiv.classList.remove('d-none');
            return;
        }

        const originalText = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = 'در حال ذخیره...';

        try {
            const response = await fetch('/accounts/api/set-new-password/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    password: password,
                    password_confirm: confirm
                })
            });

            const data = await response.json();

            if (data.success) {
                showNotificationModal('تبریک!', data.message, 'success', () => {
                    window.location.href = data.redirect_url || '/accounts/login/';
                });
            } else {
                errorDiv.innerHTML = data.error || 'خطا در ذخیره‌ی رمز';
                errorDiv.classList.remove('d-none');
                saveBtn.disabled = false;
                saveBtn.innerHTML = originalText;
            }
        } catch (error) {
            console.error('Error:', error);
            errorDiv.innerHTML = 'مشکلی در ارتباط با سرور پیش آمد';
            errorDiv.classList.remove('d-none');
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
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