// داخل فایل JS یا درون بلاک script
document.addEventListener('DOMContentLoaded', function() {
    const roleSelect = document.getElementById('role-select');
    const teamFields = document.getElementById('team-fields');
    const createNewTeamCheckbox = document.getElementById('create-new-team');
    const existingTeamField = document.getElementById('existing-team-field');
    const newTeamField = document.getElementById('new-team-field');
    const teamSlugInput = document.getElementById('team-slug');
    const teamNameInput = document.getElementById('team-name');

    // نمایش/مخفی کردن فیلدهای تیم بر اساس نقش انتخاب شده
    function toggleTeamFields() {
        if (roleSelect.value === 'team_member') {
            teamFields.style.display = 'block';
            // اضافه کردن انیمیشن smooth
            teamFields.style.animation = 'fadeIn 0.3s ease';
        } else {
            teamFields.style.display = 'none';
            // ریست کردن چک باکس و فیلدها وقتی نقش عوض میشه
            if (createNewTeamCheckbox) createNewTeamCheckbox.checked = false;
            if (teamSlugInput) {
                teamSlugInput.disabled = false;
                teamSlugInput.value = '';
            }
            if (teamNameInput) {
                teamNameInput.disabled = true;
                teamNameInput.value = '';
            }
            // مخفی کردن فیلدهای اضافی
            if (existingTeamField) existingTeamField.style.display = 'block';
            if (newTeamField) newTeamField.style.display = 'none';
        }
    }

    // تغییر فیلدها بر اساس چک باکس
    function toggleTeamTypeFields() {
        if (!createNewTeamCheckbox) return;

        if (createNewTeamCheckbox.checked) {
            // حالت ساخت تیم جدید
            existingTeamField.style.display = 'none';
            newTeamField.style.display = 'block';

            // غیرفعال کردن فیلد شناسه تیم و پاک کردن مقدارش
            if (teamSlugInput) {
                teamSlugInput.disabled = true;
                teamSlugInput.value = '';
                teamSlugInput.required = false;
            }

            // فعال کردن فیلد نام تیم
            if (teamNameInput) {
                teamNameInput.disabled = false;
                teamNameInput.required = true;
                teamNameInput.focus(); // فوکوس روی فیلد نام تیم
            }

            // اضافه کردن کلاس برای هایلایت
            newTeamField.classList.add('highlight-field');
            setTimeout(() => {
                newTeamField.classList.remove('highlight-field');
            }, 500);

        } else {
            // حالت عضویت در تیم موجود
            existingTeamField.style.display = 'block';
            newTeamField.style.display = 'none';

            // فعال کردن فیلد شناسه تیم
            if (teamSlugInput) {
                teamSlugInput.disabled = false;
                teamSlugInput.required = true;
                teamSlugInput.focus(); // فوکوس روی فیلد شناسه تیم
            }

            // غیرفعال کردن فیلد نام تیم و پاک کردن مقدارش
            if (teamNameInput) {
                teamNameInput.disabled = true;
                teamNameInput.value = '';
                teamNameInput.required = false;
            }

            // اضافه کردن کلاس برای هایلایت
            existingTeamField.classList.add('highlight-field');
            setTimeout(() => {
                existingTeamField.classList.remove('highlight-field');
            }, 500);
        }
    }

    // اضافه کردن event listenerها
    if (roleSelect) {
        roleSelect.addEventListener('change', toggleTeamFields);
    }

    if (createNewTeamCheckbox) {
        createNewTeamCheckbox.addEventListener('change', toggleTeamTypeFields);
    }

    // اجرای اولیه
    toggleTeamFields();
    toggleTeamTypeFields();
});

// فرم سابمیت
document.querySelector('form.needs-validation').onsubmit = function (event) {
    event.preventDefault();

    // فعال کردن فیلدهای غیرفعال شده قبل از ارسال
    const teamSlug = document.getElementById('team-slug');
    const teamName = document.getElementById('team-name');
    const createNewTeam = document.getElementById('create-new-team');

    // قبل از ارسال، فیلدهای مورد نیاز رو فعال کن
    if (teamSlug && (!createNewTeam || !createNewTeam.checked)) {
        teamSlug.disabled = false;
    }

    if (teamName && createNewTeam && createNewTeam.checked) {
        teamName.disabled = false;
    }

    var form = this;
    var formData = new FormData(form);

    // نمایش لوودینگ
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'در حال ثبت نام...';
    submitBtn.disabled = true;

    fetch(form.action, {
        method: "POST",
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect_url;
        } else {
            // نمایش بهتر خطاها
            if (typeof data.error === 'object') {
                let errorMsg = 'خطاهای زیر رخ داده:\n\n';
                for (let key in data.error) {
                    if (data.error[key]) {
                        errorMsg += `• ${data.error[key]}\n`;
                    }
                }
                alert(errorMsg);
            } else {
                alert(data.error);
            }
            // برگشت دکمه به حالت اول
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("خطایی رخ داده است. لطفاً دوباره تلاش کنید.");
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

// اضافه کردن انیمیشن به CSS (اگه توی فایل CSS نداری)
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .highlight-field {
        animation: highlight 0.5s ease;
    }
    
    @keyframes highlight {
        0% {
            background-color: rgba(255, 193, 7, 0.2);
            border-color: #ffc107;
        }
        100% {
            background-color: transparent;
            border-color: inherit;
        }
    }
    
    #team-fields {
        transition: all 0.3s ease;
    }
    
    #existing-team-field, #new-team-field {
        transition: all 0.3s ease;
    }
`;
document.head.appendChild(style);