/**
 * ============================================================
 * typing.js
 * افکت تایپ حرفه‌به‌حرف برای توضیحات تیم
 * پشتیبانی کامل از خطوط جدید (اینترها)
 * ============================================================
 */

(function initTypingEffect() {
    'use strict';

    // ============================================================
    // ۱. پیدا کردن المنت حاوی توضیحات
    // ============================================================
    const aboutContainer = document.querySelector('.about-text');
    if (!aboutContainer) {
        console.warn('⚠️ المنت .about-text پیدا نشد');
        return;
    }

    const paragraph = aboutContainer.querySelector('p');
    if (!paragraph) {
        console.warn('⚠️ تگ <p> داخل .about-text پیدا نشد');
        return;
    }

    // ============================================================
    // ۲. گرفتن متن کامل (با حفظ خطوط جدید)
    // ============================================================
    const fullHtml = paragraph.innerHTML || '';
    if (!fullHtml.trim()) {
        console.warn('⚠️ متنی برای تایپ وجود ندارد');
        return;
    }

    // ============================================================
    // ۳. تنظیمات
    // ============================================================
    const TYPING_SPEED = 20; // میلی‌ثانیه بین هر کاراکتر

    // ============================================================
    // ۴. پاک کردن محتوای داخل <p> و آماده‌سازی برای تایپ
    // ============================================================
    paragraph.innerHTML = '';

    const textSpan = document.createElement('span');
    textSpan.className = 'typing-text';
    textSpan.style.cssText = 'display: inline; white-space: pre-wrap;';

    const cursor = document.createElement('span');
    cursor.className = 'typing-cursor';
    cursor.style.cssText = `
        display: inline-block;
        width: 2px;
        height: 1.2em;
        background-color: var(--bs-accent, #6c5ce7);
        margin-right: 2px;
        vertical-align: text-bottom;
        animation: blink-cursor 0.8s step-end infinite;
    `;

    paragraph.appendChild(textSpan);
    paragraph.appendChild(cursor);

    // ============================================================
    // ۵. اضافه کردن استایل کرسر به صفحه
    // ============================================================
    function addCursorStyles() {
        const styleId = 'typing-cursor-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            @keyframes blink-cursor {
                0%, 100% { opacity: 1; }
                50% { opacity: 0; }
            }
            .typing-cursor {
                display: inline-block;
                animation: blink-cursor 0.8s step-end infinite;
            }
            .typing-text {
                white-space: pre-wrap !important;
                word-break: break-word;
            }
        `;
        document.head.appendChild(style);
    }
    addCursorStyles();

    // ============================================================
    // ۶. تبدیل متن به آرایه‌ای از کاراکترها (با حفظ خطوط جدید)
    // ============================================================
    const chars = [];


    const textWithNewLines = fullHtml
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<p>/gi, '')
        .replace(/<\/p>/gi, '')
        .replace(/<[^>]*>/g, '');

    for (let i = 0; i < textWithNewLines.length; i++) {
        chars.push(textWithNewLines[i]);
    }

    // ============================================================
    // ۷. شروع تایپ (با پشتیبانی از خطوط جدید)
    // ============================================================
    let charIndex = 0;

    function typeNextChar() {
        if (charIndex >= chars.length) {
            cursor.style.display = 'none';
            return;
        }

        const currentText = chars.slice(0, charIndex + 1).join('');

        textSpan.innerHTML = currentText.replace(/\n/g, '<br>');

        charIndex++;

        setTimeout(typeNextChar, TYPING_SPEED);
    }

    setTimeout(typeNextChar, 300);

})();