// اسکرول انیمیشن
const revealElements = document.querySelectorAll('.scroll-reveal');
const revealOnScroll = () => revealElements.forEach(el => {
    if (el.getBoundingClientRect().top < window.innerHeight - 100) el.classList.add('revealed');
});
window.addEventListener('scroll', revealOnScroll);
window.addEventListener('load', revealOnScroll);

// شمارنده آمار
const observer = new IntersectionObserver((entries) => entries.forEach(entry => {
    const el = entry.target;
    if (!entry.isIntersecting) return;
    const finalNum = parseInt(el.getAttribute('data-final') || el.textContent.replace(/[^0-9]/g, ''));
    if (!el.getAttribute('data-final')) el.setAttribute('data-final', finalNum);
    if (isNaN(finalNum) || finalNum <= 0) return;
    if (el.timer) clearInterval(el.timer);
    el.textContent = '0';
    let current = 0;
    const step = finalNum / 50;
    el.timer = setInterval(() => {
        current += step;
        if (current >= finalNum) {
            el.textContent = finalNum.toLocaleString('fa-IR');
            clearInterval(el.timer);
            el.timer = null;
        } else el.textContent = Math.floor(current).toLocaleString('fa-IR');
    }, 30);
}), {threshold: 0.3});
document.querySelectorAll('.stat-number').forEach(el => observer.observe(el));

// هدر اسکرول
const header = document.querySelector('.navbar');
if (header) window.addEventListener('scroll', () => header.classList.toggle('navbar-stuck', window.scrollY > 50));

// ذرات پس‌زمینه
const particlesContainer = document.getElementById('particles');
if (particlesContainer) for (let i = 0; i < 50; i++) {
    const p = document.createElement('span');
    const size = Math.random() * 4 + 2;
    p.style.width = size + 'px';
    p.style.height = size + 'px';
    p.style.left = Math.random() * 100 + '%';
    p.style.animationDelay = Math.random() * 15 + 's';
    p.style.animationDuration = Math.random() * 10 + 10 + 's';
    particlesContainer.appendChild(p);
}

// تغییر متن پلتفرم‌ها
const platforms = [{name: "تلگرام", class: "platform-telegram"}, {name: "بله", class: "platform-bale"}, {
    name: "ایتا",
    class: "platform-eitaa"
}, {name: "روبیکا", class: "platform-rubika"}, {name: "اینستاگرام", class: "platform-instagram"}, {
    name: "سروش پلاس",
    class: "platform-soroush"
}];
let index = 0;
const textElement = document.getElementById("changing-text");
if (textElement) {
    textElement.classList.add(platforms[0].class);
    textElement.textContent = platforms[0].name;
    setInterval(() => {
        index = (index + 1) % platforms.length;
        textElement.style.opacity = "0";
        setTimeout(() => {
            textElement.className = "";
            textElement.classList.add(platforms[index].class);
            textElement.textContent = platforms[index].name;
            textElement.style.opacity = "1";
        }, 200);
    }, 4000);
}