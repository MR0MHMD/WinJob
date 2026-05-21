// team_form.js
(function() {
    // دریافت تنظیمات از پنجره (تزریق شده توسط قالب)
    const config = window.teamFormConfig || {};
    const logoInputId = config.logoInputId;
    const teamId = config.teamId;

    // عناصر DOM
    const dropZone = document.getElementById('dropZone');
    const fileInput = logoInputId ? document.getElementById(logoInputId) : null;
    const previewImg = document.getElementById('logoPreview');
    const slugInput = document.getElementById('slug-input');
    const slugFeedback = document.getElementById('slug-feedback');
    const submitBtn = document.querySelector('button[type="submit"]');

    // ---- توابع مربوط به تصویر ----
    function handleFile(file) {
        if (!file || !file.type.startsWith('image/')) {
            alert('لطفاً فقط فایل تصویری آپلود کنید.');
            if (fileInput) fileInput.value = '';
            if (previewImg && previewImg.src && !previewImg.src.includes('default')) {
            }
            return;
        }

        if (previewImg) {
            const reader = new FileReader();
            reader.onload = (e) => { previewImg.src = e.target.result; };
            reader.readAsDataURL(file);
        }
    }

    // دراپ زون
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file) {
                fileInput.files = e.dataTransfer.files;
                handleFile(file);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleFile(e.target.files[0]);
        });
    }

    // ---- اعتبارسنجی اسلاگ ----
    let debounceTimer;

    function validateSlug() {
        if (!slugInput || !slugFeedback) return;
        const slug = slugInput.value.trim();
        if (!slug) {
            slugFeedback.innerHTML = '<span class="text-muted">خالی گذاشتن = تولید خودکار اسلاگ</span>';
            if (submitBtn) submitBtn.disabled = false;
            return;
        }

        const slugRegex = /^[a-zA-Z0-9_-]+$/;
        if (!slugRegex.test(slug)) {
            slugFeedback.innerHTML = '<span class="text-danger">❌ فقط حروف انگلیسی، اعداد، خط تیره و زیرخط مجاز است.</span>';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        fetch(`/content_team/team/check-slug/?slug=${encodeURIComponent(slug)}&team_id=${teamId}`)
            .then(response => response.json())
            .then(data => {
                if (data.available) {
                    slugFeedback.innerHTML = `<span class="text-success">✅ ${data.message}</span>`;
                    if (submitBtn) submitBtn.disabled = false;
                } else {
                    slugFeedback.innerHTML = `<span class="text-danger">❌ ${data.message}</span>`;
                    if (submitBtn) submitBtn.disabled = true;
                }
            })
            .catch(error => {
                console.error('خطا در بررسی اسلاگ:', error);
                slugFeedback.innerHTML = '<span class="text-warning">⚠️ خطا در ارتباط با سرور</span>';
                if (submitBtn) submitBtn.disabled = false;
            });
    }

    if (slugInput) {
        validateSlug();
        slugInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(validateSlug, 400);
        });
    }
})();