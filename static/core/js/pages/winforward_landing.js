/* WinForward Visual Experience v2 — Spotlight Hover, Animated Counters, Hero Live Cycle & Interactive Simulators */
document.addEventListener("DOMContentLoaded", function () {
    // 1. Scroll Reveal with subtle stagger
    const revealEls = document.querySelectorAll("[data-wfl-reveal]");
    if ("IntersectionObserver" in window && revealEls.length) {
        const io = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        io.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.1 }
        );
        revealEls.forEach(function (el, idx) {
            el.style.transitionDelay = Math.min((idx % 4) * 70, 210) + "ms";
            io.observe(el);
        });
    } else {
        revealEls.forEach(function (el) { el.classList.add("is-visible"); });
    }

    // 2. Mouse-Tracking Spotlight Glow on all .wfl-spot-card elements
    document.querySelectorAll(".wfl-spot-card").forEach(function (card) {
        card.addEventListener("mousemove", function (e) {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--mx", x + "px");
            card.style.setProperty("--my", y + "px");
        });
    });

    // 3. Smooth Counter Animation
    const counters = document.querySelectorAll("[data-wfl-count]");
    if ("IntersectionObserver" in window && counters.length) {
        const cio = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    const el = entry.target;
                    const target = parseInt(el.dataset.wflCount || "0", 10);
                    const suffix = el.dataset.wflSuffix || "";
                    const duration = 1100;
                    const start = performance.now();
                    function tick(now) {
                        const progress = Math.min((now - start) / duration, 1);
                        const eased = 1 - Math.pow(1 - progress, 3);
                        const current = Math.round(target * eased);
                        el.textContent = current.toLocaleString("fa-IR") + suffix;
                        if (progress < 1) requestAnimationFrame(tick);
                    }
                    requestAnimationFrame(tick);
                    cio.unobserve(el);
                });
            },
            { threshold: 0.3 }
        );
        counters.forEach(function (c) { cio.observe(c); });
    }

    // 4. Hero Live Message Rotation (cycles realistic posts inside the Hero 3D Stage)
    const heroPostText = document.getElementById("wflHeroLivePost");
    const heroOldSig = document.getElementById("wflHeroOldSig");
    const heroNewSig = document.getElementById("wflHeroNewSig");
    if (heroPostText && heroOldSig && heroNewSig) {
        const slides = [
            {
                text: "گزارش ویژه بازار دیجیتال امروز منتشر شد؛ برای بررسی جزئیات کامل همراه ما باشید...",
                oldSig: "@source_channel",
                newSig: "✨ جایگزین با امضای اختصاصی هر کانال",
            },
            {
                text: "تخفیف ویژه جشنواره پاییزه تا ساعت ۲۴ امشب تمدید شد؛ لینک سفارش در کپشن 👇",
                oldSig: "کانال لذت دانایی · @lezat",
                newSig: "✨ بازسازی خودکار برای بله، ایتا، تلگرام و روبیکا",
            },
            {
                text: "اطلاعیه فوری تیم محتوا: زمان وبینار آموزش رشد کانال‌ها فردا ساعت ۲۰ برگزار می‌شود.",
                oldSig: "t.me/old_media | eitaa.com/old",
                newSig: "✨ انتشار هم‌زمان در ۵ پیام‌رسان با یک کلیک",
            },
        ];
        let sIdx = 0;
        setInterval(function () {
            sIdx = (sIdx + 1) % slides.length;
            const item = slides[sIdx];
            heroPostText.style.opacity = "0";
            setTimeout(function () {
                heroPostText.textContent = item.text;
                heroOldSig.textContent = item.oldSig;
                heroNewSig.textContent = item.newSig;
                heroPostText.style.opacity = "1";
            }, 220);
        }, 4200);
    }

    // 5. Interactive AI Signature Demo
    const aiVariants = {
        custom: {
            badge: "حذف امضای مبدا + امضای اختصاصی شما",
            output:
                "نکته طلایی امروز برای رشد کانال‌های محتوایی:\nانتشار منظم در ساعات اوج بازدید، نرخ تعامل را تا ۲ برابر بالا می‌برد.\n\n✨ رسانه تخصصی وین‌جاب\n🆔 @winjob_official",
        },
        bale: {
            badge: "بازسازی هوشمند برای بله",
            output:
                "نکته طلایی امروز برای رشد کانال‌های محتوایی:\nانتشار منظم در ساعات اوج بازدید، نرخ تعامل را تا ۲ برابر بالا می‌برد.\n\nدر کانال وین‌جاب با ما همراه باشید 👇\n🆔 [کانال بله](https://ble.ir/winjob)",
        },
        eitaa: {
            badge: "بازسازی هوشمند برای ایتا",
            output:
                "نکته طلایی امروز برای رشد کانال‌های محتوایی:\nانتشار منظم در ساعات اوج بازدید، نرخ تعامل را تا ۲ برابر بالا می‌برد.\n\nدر کانال وین‌جاب با ما همراه باشید 👇\n🆔 [کانال ایتا](https://eitaa.com/winjob)",
        },
    };

    const aiTabs = document.querySelectorAll("[data-wfl-ai-variant]");
    const aiOut = document.getElementById("wflAiDemoOutput");
    const aiBadge = document.getElementById("wflAiDemoBadge");

    aiTabs.forEach(function (btn) {
        btn.addEventListener("click", function () {
            const key = btn.dataset.wflAiVariant;
            const data = aiVariants[key];
            if (!data || !aiOut) return;

            aiTabs.forEach(function (b) { b.classList.toggle("is-active", b === btn); });
            aiOut.classList.remove("is-scanning");
            void aiOut.offsetWidth;
            aiOut.classList.add("is-scanning");
            if (aiBadge) aiBadge.textContent = data.badge;

            setTimeout(function () {
                aiOut.textContent = data.output;
            }, 260);
        });
    });

    // 6. Interactive Live 5-Platform Broadcast Timeline Simulator
    const simBtn = document.getElementById("wflRunLiveSimBtn");
    const simBox = document.getElementById("wflLiveSimBox");
    if (simBtn && simBox) {
        let running = false;
        const frames = [
            "درخواست شما در حال اجراست ⚙️\n\n📥 دانلود از تلگرام: در حال انجام ⏳\n✨ افزودن امضای اختصاصی: در صف انتظار 🕒\n📤 ارسال به تلگرام: در صف انتشار 🕒\n📤 ارسال به بله: در صف انتشار 🕒\n📤 ارسال به ایتا: در صف انتشار 🕒\n📤 ارسال به روبیکا: در صف انتشار 🕒\n📤 ارسال به سروش‌پلاس: در صف انتشار 🕒",
            "درخواست شما در حال اجراست ⚙️\n\n📥 دانلود از تلگرام: انجام شد ✅\n✨ افزودن امضای اختصاصی: در حال انجام ⏳\n📤 ارسال به تلگرام: در صف انتشار 🕒\n📤 ارسال به بله: در صف انتشار 🕒\n📤 ارسال به ایتا: در صف انتشار 🕒\n📤 ارسال به روبیکا: در صف انتشار 🕒\n📤 ارسال به سروش‌پلاس: در صف انتشار 🕒",
            "درخواست شما در حال اجراست ⚙️\n\n📥 دانلود از تلگرام: انجام شد ✅\n✨ افزودن امضای اختصاصی: انجام شد ✅\n📤 ارسال به تلگرام: ارسال شد ✅\n📤 ارسال به بله: در حال ارسال 🚀\n📤 ارسال به ایتا: در صف انتشار 🕒\n📤 ارسال به روبیکا: در صف انتشار 🕒\n📤 ارسال به سروش‌پلاس: در صف انتشار 🕒",
            "درخواست شما در حال اجراست ⚙️\n\n📥 دانلود از تلگرام: انجام شد ✅\n✨ افزودن امضای اختصاصی: انجام شد ✅\n📤 ارسال به تلگرام: ارسال شد ✅\n📤 ارسال به بله: ارسال شد ✅\n📤 ارسال به ایتا: ارسال شد ✅\n📤 ارسال به روبیکا: در حال ارسال 🚀\n📤 ارسال به سروش‌پلاس: در صف انتشار 🕒",
            "عملیات انجام شد ✅\nوضعیت ارسال: 🟢 موفق\nارسال موفق به ۵ از ۵ کانال\nتعداد توکن مصرفی: ۲۲ توکن\n🔗 لینک گزارش عمومی آماده اشتراک‌گذاری با کارفرما!",
        ];

        simBtn.addEventListener("click", function () {
            if (running) return;
            running = true;
            simBtn.disabled = true;
            const origText = simBtn.innerHTML;
            simBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> در حال شبیه‌سازی...';

            frames.forEach(function (text, idx) {
                setTimeout(function () {
                    simBox.textContent = text;
                    if (idx === frames.length - 1) {
                        running = false;
                        simBtn.disabled = false;
                        simBtn.innerHTML = origText;
                    }
                }, idx * 720);
            });
        });
    }
});
