/* انیمیشن سبک و پیش‌نمایش محلی وین دایرکت؛ هیچ درخواستی به سرور ارسال نمی‌شود. */
(() => {
    'use strict';

    const shells = document.querySelectorAll('.wd-shell');
    if (!shells.length) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduceMotion && 'IntersectionObserver' in window) {
        shells.forEach((shell) => shell.classList.add('wd-motion-ready'));
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('wd-visible');
                observer.unobserve(entry.target);
            });
        }, { threshold: .12, rootMargin: '0px 0px 50px 0px' });
        document.querySelectorAll('.wd-shell [data-wd-reveal]').forEach((item) => observer.observe(item));
    }

    const demo = document.querySelector('[data-wd-demo]');
    if (!demo) return;

    const examples = {
        price: {
            comment: 'قیمت این محصول چنده؟',
            condition: 'شامل «قیمت»',
            response: 'سلام! برای دریافت جزئیات قیمت، اطلاعات محصول را بررسی کنید.'
        },
        link: {
            comment: 'لینک محصول رو می‌فرستید؟',
            condition: 'شامل «لینک»',
            response: 'سلام! لینک محصول را می‌توانید از صفحهٔ معرفی آن دنبال کنید.'
        },
        consult: {
            comment: 'برای انتخاب محصول مشاوره می‌خوام.',
            condition: 'شامل «مشاوره»',
            response: 'سلام! سؤالتان را مطرح کنید تا مسیر مناسب را به شما معرفی کنیم.'
        }
    };

    demo.querySelectorAll('[data-wd-variant]').forEach((button) => {
        button.addEventListener('click', () => {
            const example = examples[button.dataset.wdVariant];
            if (!example) return;
            demo.querySelectorAll('[data-wd-variant]').forEach((tab) => {
                const active = tab === button;
                tab.classList.toggle('is-active', active);
                tab.setAttribute('aria-pressed', String(active));
            });
            demo.querySelector('[data-wd-comment]').textContent = example.comment;
            demo.querySelector('[data-wd-condition]').textContent = example.condition;
            demo.querySelector('[data-wd-response]').textContent = example.response;
        });
    });
})();
