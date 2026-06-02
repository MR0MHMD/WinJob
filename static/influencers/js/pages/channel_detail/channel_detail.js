// ==================== انیمیشن‌ها و اینترکشن‌های عمومی ====================

// مودال درخواست همکاری
const orderBtn = document.getElementById('orderBtn');
const orderModal = new bootstrap.Modal(document.getElementById('orderModal'));
if (orderBtn) {
    orderBtn.addEventListener('click', () => orderModal.show());
}

// اشتراک‌گذاری پیشرفته
let shareModal = null;

function shareProfile() {
    if (navigator.share) {
        navigator.share({
            title: window.channelData?.channelName || 'پروفایل اینفلوئنسر',
            text: 'پروفایل اینفلوئنسر در WinJob',
            url: window.location.href
        }).catch(() => {
        });
    } else {
        if (!shareModal) {
            shareModal = new bootstrap.Modal(document.getElementById('shareModal'));
        }
        document.getElementById('shareUrl').value = window.location.href;
        shareModal.show();
    }
}

function copyToClipboard() {
    const urlInput = document.getElementById('shareUrl');
    urlInput.select();
    urlInput.setSelectionRange(0, 99999);
    document.execCommand('copy');
    if (typeof showNotificationModal !== 'undefined') {
        showNotificationModal('موفق', 'لینک پروفایل با موفقیت کپی شد!', 'success');
    }
}

function contactSupport() {
    if (typeof showNotificationModal !== 'undefined') {
        showNotificationModal('پشتیبانی', 'لطفاً از طریق صفحه "تماس با ما" با پشتیبانی در ارتباط باشید.', 'info');
    }
}

function reportUser() {
    if (typeof showNotificationModal !== 'undefined') {
        showNotificationModal('گزارش تخلف', 'گزارش شما با موفقیت ثبت شد. تیم ما ظرف 24 ساعت بررسی خواهد کرد.', 'warning');
    }
}

// ==================== انیمیشن شمارنده ====================
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

// ==================== کاروسل نظرات (اسکرول افقی) ====================
const reviewsContainer = document.getElementById('reviewsContainer');
const prevBtn = document.getElementById('prevReview');
const nextBtn = document.getElementById('nextReview');

if (reviewsContainer && prevBtn && nextBtn) {
    let scrollPosition = 0;
    const cardWidth = 380;
    prevBtn.addEventListener('click', () => {
        scrollPosition = Math.max(0, scrollPosition - cardWidth);
        reviewsContainer.scrollTo({left: scrollPosition, behavior: 'smooth'});
    });
    nextBtn.addEventListener('click', () => {
        const maxScroll = reviewsContainer.scrollWidth - reviewsContainer.clientWidth;
        scrollPosition = Math.min(maxScroll, scrollPosition + cardWidth);
        reviewsContainer.scrollTo({left: scrollPosition, behavior: 'smooth'});
    });
}

// ==================== انیمیشن تایپ‌رایتر ====================
const aboutText = document.getElementById('aboutText');
if (aboutText) {
    const originalText = aboutText.innerText;
    aboutText.innerText = '';
    let i = 0;

    function typeWriter() {
        if (i < originalText.length) {
            aboutText.innerText += originalText.charAt(i);
            i++;
            setTimeout(typeWriter, 30);
        }
    }

    const typeObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            typeWriter();
            typeObserver.disconnect();
        }
    }, {threshold: 0.3});
    typeObserver.observe(aboutText);
}

// ==================== اسکرول انیمیشن AOS ====================
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

// ==================== افکت هدر پارالاکس ====================
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

// ==================== راه‌اندازی tooltips ====================
if (typeof bootstrap !== 'undefined') {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });
}