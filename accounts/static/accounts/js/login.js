document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.querySelector('#signin-modal form');
    if (!loginForm) return;

    loginForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const form = this;
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;

        submitBtn.innerHTML = 'در حال ورود...';
        submitBtn.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await response.json();

            if (data.success) {
                // گرفتن آدرس ذخیره شده برای بعد از لاگین
                let redirectUrl = sessionStorage.getItem('redirectAfterLogin') || '/';
                sessionStorage.removeItem('redirectAfterLogin');

                // بستن مودال
                const modal = bootstrap.Modal.getInstance(document.getElementById('signin-modal'));
                if (modal) modal.hide();

                // رفتن به آدرس
                window.location.href = redirectUrl;
            } else {
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('خطا در ورود', data.error, 'error');
                } else {
                    alert(data.error);
                }
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        } catch (error) {
            console.error("Error:", error);
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('خطا', 'مشکلی در ارتباط با سرور رخ داده است', 'error');
            } else {
                alert('مشکلی در ارتباط با سرور رخ داده است');
            }
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
});