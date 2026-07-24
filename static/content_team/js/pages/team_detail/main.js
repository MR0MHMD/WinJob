/**
 * ============================================================
 * team_detail_core.js
 * توابع پایه و عمومی صفحه جزئیات تیم
 * شامل: اشتراک‌گذاری، کپی لینک، QR Code، افکت‌ها
 * ============================================================
 */

// ============================================================
// ۱. مودال درخواست همکاری
// ============================================================
(function initOrderModal() {
    const orderBtn = document.getElementById('orderBtn');
    const orderModalEl = document.getElementById('orderModal');

    if (orderBtn && orderModalEl) {
        const modal = new bootstrap.Modal(orderModalEl);
        orderBtn.addEventListener('click', function (e) {
            e.preventDefault();
            modal.show();
        });
    }
})();


// ============================================================
// ۲. اشتراک‌گذاری پروفایل
// ============================================================
let shareModalInstance = null;

window.shareProfile = function () {
    const teamName = document.querySelector('.profile-name')?.textContent?.trim() || 'تیم';
    const shareText = `پروفایل تیم ${teamName} در WinJob`;

    // اولویت ۱: Web Share API
    if (navigator.share) {
        navigator.share({
            title: `پروفایل ${teamName}`,
            text: shareText,
            url: window.location.href
        }).catch(function (err) {
            // خطای کنسل شدن توسط کاربر رو نادیده میگیریم
            if (err.name !== 'AbortError') {
                console.warn('اشتراک‌گذاری ناموفق:', err);
                fallbackShare();
            }
        });
        return;
    }

    // اولویت ۲: روش جایگزین (نمایش مودال)
    fallbackShare();
};

function fallbackShare() {
    const modalEl = document.getElementById('shareModal');
    if (!modalEl) return;

    if (!shareModalInstance) {
        shareModalInstance = new bootstrap.Modal(modalEl);
    }

    const urlInput = document.getElementById('shareUrl');
    if (urlInput) {
        urlInput.value = window.location.href;
    }

    shareModalInstance.show();
}


// ============================================================
// ۳. کپی در کلیپ‌بورد
// ============================================================
window.copyToClipboard = function () {
    const urlInput = document.getElementById('shareUrl');
    if (!urlInput) return;

    // روش مدرن
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(urlInput.value)
            .then(function () {
                showCopyFeedback(true);
            })
            .catch(function () {
                fallbackCopy(urlInput);
            });
    } else {
        fallbackCopy(urlInput);
    }
};

function fallbackCopy(input) {
    input.select();
    input.setSelectionRange(0, 99999);

    try {
        document.execCommand('copy');
        showCopyFeedback(true);
    } catch (err) {
        showCopyFeedback(false);
        console.warn('کپی ناموفق:', err);
    }
}

function showCopyFeedback(success) {
    const btn = document.querySelector('.share-copy-btn');
    if (!btn) return;

    const originalHtml = btn.innerHTML;
    btn.innerHTML = success ?
        '<i class="fi-check-circle text-success"></i>' :
        '<i class="fi-x-circle text-danger"></i>';

    setTimeout(function () {
        btn.innerHTML = originalHtml;
    }, 2000);
}


// ============================================================
// ۴. اشتراک‌گذاری QR Code
// ============================================================
window.shareQrCode = function (qrUrl, name) {
    const safeName = name || 'team';

    // Web Share API با فایل
    if (navigator.share) {
        fetch(qrUrl)
            .then(function (res) {
                if (!res.ok) throw new Error('Network response was not ok');
                return res.blob();
            })
            .then(function (blob) {
                const file = new File([blob], `QR_${safeName}.png`, {type: 'image/png'});
                navigator.share({
                    title: `QR Code ${safeName}`,
                    text: `QR Code ${safeName} - WinJob`,
                    files: [file]
                }).catch(function (err) {
                    if (err.name !== 'AbortError') {
                        downloadQrCode(qrUrl, safeName);
                    }
                });
            })
            .catch(function () {
                downloadQrCode(qrUrl, safeName);
            });
    } else {
        downloadQrCode(qrUrl, safeName);
    }
};

function downloadQrCode(url, name) {
    const link = document.createElement('a');
    link.href = url;
    link.download = `QR_${name}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}


// ============================================================
// ۵. افکت پارالاکس هدر
// ============================================================
(function initParallax() {
    const header = document.querySelector('.profile-cover');
    if (!header) return;

    const bg = header.querySelector('.profile-cover-bg');
    if (!bg) return;

    let ticking = false;

    window.addEventListener('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(function () {
                const scrolled = window.pageYOffset;
                bg.style.transform = `translateY(${scrolled * 0.3}px) scale(1.1)`;
                ticking = false;
            });
            ticking = true;
        }
    });
})();


// ============================================================
// ۶. انیمیشن AOS (با Intersection Observer)
// ============================================================
(function initAOS() {
    const animatedElements = document.querySelectorAll('[data-aos]');
    if (!animatedElements.length) return;

    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('aos-animate');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    animatedElements.forEach(function (el) {
        observer.observe(el);
    });
})();


// ============================================================
// ۷. تماس با پشتیبانی (مودال)
// ============================================================
window.contactSupport = function () {
    // TODO: پیاده‌سازی باز کردن چت پشتیبانی
    // یا نمایش مودال تماس
    console.log('تماس با پشتیبانی');
    // می‌توانید یک مودال یا ریدایرکت به صفحه تیکت اضافه کنید
};