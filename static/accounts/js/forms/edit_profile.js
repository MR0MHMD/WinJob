document.addEventListener('DOMContentLoaded', function () {
    const avatarInput = document.getElementById('avatar-upload');
    const avatarPreview = document.getElementById('avatar-preview');
    const avatarPlaceholder = document.getElementById('avatar-placeholder');

    if (avatarInput) {
        avatarInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                if (file.size > 2 * 1024 * 1024) {
                    if (typeof toastManager !== 'undefined') {
                        toastManager.show('فرمت سنگین: حجم عکس نباید فراتر از 2 مگابایت باشد.', 'error');
                    } else {
                        alert('حجم فایل انتخابی بیش از حد مجاز (2 مگابایت) است.');
                    }
                    this.value = '';
                    return;
                }

                const reader = new FileReader();
                reader.onload = function (e) {
                    if (avatarPlaceholder) {
                        avatarPlaceholder.classList.add('d-none');
                    }
                    avatarPreview.classList.remove('d-none');
                    avatarPreview.style.opacity = '0.3';

                    setTimeout(() => {
                        avatarPreview.src = e.target.result;
                        avatarPreview.style.opacity = '1';
                    }, 200);
                }
                reader.readAsDataURL(file);
            }
        });
    }
});