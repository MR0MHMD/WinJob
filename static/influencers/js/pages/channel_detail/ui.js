// ==================== اینترکشن‌های UI ====================

document.addEventListener('DOMContentLoaded', function() {

    // ---------- مودال درخواست همکاری ----------
    const orderBtn = document.getElementById('orderBtn');
    const orderModal = document.getElementById('orderModal');
    if (orderBtn && orderModal) {
        const modal = new bootstrap.Modal(orderModal);
        orderBtn.addEventListener('click', () => modal.show());
    }

    // ---------- اشتراک‌گذاری پروفایل ----------
    let shareModal = null;
    window.shareProfile = function() {
        if (navigator.share) {
            navigator.share({
                title: window.channelData?.channelName || 'پروفایل اینفلوئنسر',
                text: 'پروفایل اینفلوئنسر در WinJob',
                url: window.location.href
            }).catch(() => {});
        } else {
            if (!shareModal) {
                shareModal = new bootstrap.Modal(document.getElementById('shareModal'));
            }
            document.getElementById('shareUrl').value = window.location.href;
            shareModal.show();
        }
    };

    window.copyToClipboard = function() {
        const urlInput = document.getElementById('shareUrl');
        urlInput.select();
        urlInput.setSelectionRange(0, 99999);
        document.execCommand('copy');
        if (typeof showNotificationModal !== 'undefined') {
            showNotificationModal('موفق', 'لینک پروفایل با موفقیت کپی شد!', 'success');
        }
    };

    // ---------- اشتراک‌گذاری QR Code ----------
    window.shareQrCode = function(qrUrl, name) {
        if (navigator.share) {
            fetch(qrUrl)
                .then(res => {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.blob();
                })
                .then(blob => {
                    const file = new File([blob], `QR_${name}.webp`, { type: 'image/webp' });
                    navigator.share({
                        title: `QR Code ${name}`,
                        text: `QR Code ${name} - WinJob`,
                        files: [file]
                    }).catch(err => {
                        if (err.name !== 'AbortError') {
                            console.log('Share cancelled or failed');
                        }
                    });
                })
                .catch(err => {
                    console.log('Fetch error:', err);
                    const link = document.createElement('a');
                    link.href = qrUrl;
                    link.download = `QR_${name}.webp`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                });
        } else {
            const link = document.createElement('a');
            link.href = qrUrl;
            link.download = `QR_${name}.webp`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    // ---------- انیمیشن شمارنده ----------
    function animateCounter(element, target) {
        let current = 0;
        const increment = target / 50;
        const updateCounter = () => {
            current += increment;
            if (current < target) {
                element.innerHTML = Math.floor(current).toLocaleString('fa-IR');
                requestAnimationFrame(updateCounter);
            } else {
                element.innerHTML = target.toLocaleString('fa-IR');
            }
        };
        updateCounter();
    }

    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = parseInt(counter.dataset.target);
                if (!isNaN(target) && counter.innerHTML !== target.toLocaleString('fa-IR')) {
                    animateCounter(counter, target);
                }
                counterObserver.unobserve(counter);
            }
        });
    }, {threshold: 0.5});

    document.querySelectorAll('.counter').forEach(counter => {
        counterObserver.observe(counter);
    });

    // ---------- انیمیشن تایپ‌رایتر (نسخه نهایی) ----------
const aboutText = document.getElementById('aboutText');
if (aboutText) {
    // دریافت متن اصلی با حفظ فرمت
    const originalHTML = aboutText.innerHTML;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = originalHTML;
    const originalText = tempDiv.textContent || tempDiv.innerText || '';

    // پاک کردن محتوا برای شروع تایپ
    aboutText.innerHTML = '';
    let i = 0;
    let isTyping = false;

    function typeWriter() {
        if (i < originalText.length) {
            const char = originalText.charAt(i);

            // مدیریت کاراکترهای خاص
            switch(char) {
                case ' ':
                    aboutText.innerHTML += ' ';
                    break;
                case '\n':
                    aboutText.innerHTML += '<br>';
                    break;
                case '\t':
                    aboutText.innerHTML += '&nbsp;&nbsp;&nbsp;&nbsp;';
                    break;
                case '<':
                    aboutText.innerHTML += '&lt;';
                    break;
                case '>':
                    aboutText.innerHTML += '&gt;';
                    break;
                case '&':
                    aboutText.innerHTML += '&amp;';
                    break;
                default:
                    aboutText.innerHTML += char;
            }

            i++;
            setTimeout(typeWriter, 25);
        }
    }

    const typeObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && !isTyping) {
            isTyping = true;
            typeWriter();
            typeObserver.disconnect();
        }
    }, {threshold: 0.3});
    typeObserver.observe(aboutText);
}

    // ---------- اسکرول انیمیشن AOS ----------
    const animatedElements = document.querySelectorAll('[data-aos]');
    const aosObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('aos-animate');
                aosObserver.unobserve(entry.target);
            }
        });
    }, {threshold: 0.1, rootMargin: '0px 0px -50px 0px'});
    animatedElements.forEach(el => aosObserver.observe(el));

    // ---------- افکت هدر پارالاکس ----------
    window.addEventListener('scroll', () => {
        const header = document.querySelector('.profile-cover');
        if (header) {
            const scrolled = window.pageYOffset;
            const bg = header.querySelector('.profile-cover-bg');
            if (bg) {
                bg.style.transform = `translateY(${scrolled * 0.3}px) scale(1.1)`;
            }
        }
    });

    // ---------- راه‌اندازی tooltips ----------
    if (typeof bootstrap !== 'undefined') {
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
            new bootstrap.Tooltip(el);
        });
    }
});