// مودال درخواست همکاری
const orderBtn = document.getElementById('orderBtn');
const orderModal = new bootstrap.Modal(document.getElementById('orderModal'));

if (orderBtn) {
    orderBtn.addEventListener('click', () => orderModal.show());
}

// اشتراک‌گذاری
let shareModal = null;

function shareProfile() {
    if (navigator.share) {
        navigator.share({
            title: '{{ team.name }}',
            text: 'پروفایل تیم {{ team.name }} در WinJob',
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
}

// انیمیشن AOS
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

// افکت پارالاکس هدر
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