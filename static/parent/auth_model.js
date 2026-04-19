// مدیریت خودکار مودال لاگین برای صفحات protected
    document.addEventListener('DOMContentLoaded', function() {

        // ========== 1. مدیریت لینک‌های معمولی ==========
        // به همه لینک‌هایی که به آدرس‌های protected میرن، کلیک لیسنر اضافه کن
        const protectedPaths = [
            '/profile/', '/dashboard/', '/influencers/',
            '/advertisers/', '/notifications/', '/campaigns/'
        ];

        // تابع برای چک کردن اینکه آیا لینک به آدرس protected هست یا نه
        function isProtectedUrl(url) {
            if (!url) return false;
            for (let path of protectedPaths) {
                if (url.includes(path)) {
                    return true;
                }
            }
            return false;
        }

        // گرفتن همه لینک‌های صفحه
        document.querySelectorAll('a').forEach(link => {
            const href = link.getAttribute('href');
            if (href && isProtectedUrl(href)) {
                // اگه لینک قبلاً کلاس خاصی نداره، بهش یه کلاس میدیم برای تشخیص
                if (!link.classList.contains('require-login')) {
                    link.classList.add('require-login');
                }
            }
        });

        // مدیریت کلیک روی لینک‌های require-login
        document.body.addEventListener('click', function(e) {
            let target = e.target;
            while (target && target.tagName !== 'A') {
                target = target.parentElement;
            }

            if (!target || !target.href) return;

            // اگه لینک کلاس require-login داشت یا آدرسش protected بود
            if (target.classList.contains('require-login') || isProtectedUrl(target.href)) {
                // چک کردن لاگین بودن کاربر
                const isAuthenticated = window.userIsAuthenticated;

                if (!isAuthenticated) {
                    e.preventDefault();
                    const nextUrl = target.getAttribute('href');
                    sessionStorage.setItem('redirectAfterLogin', nextUrl);
                    const loginModal = new bootstrap.Modal(document.getElementById('signin-modal'));
                    loginModal.show();
                }
            }
        });

        // ========== 2. مدیریت درخواست‌های Ajax ==========
        // ذخیره کردن fetch اصلی
        const originalFetch = window.fetch;

        // override کردن fetch برای مدیریت خودکار 403
        window.fetch = function(...args) {
            return originalFetch.apply(this, args).then(response => {
                // اگه پاسخ 403 بود و هدر X-Login-Required رو داشت
                if (response.status === 403 && response.headers.get('X-Login-Required')) {
                    // خوندن پاسخ به صورت json
                    return response.clone().json().catch(() => ({})).then(data => {
                        // گرفتن آدرس مقصد
                        const nextUrl = response.headers.get('X-Next-Url') || data.next_url || window.location.href;

                        // ذخیره آدرس برای بعد از لاگین
                        sessionStorage.setItem('redirectAfterLogin', nextUrl);

                        // باز کردن مودال لاگین
                        const loginModal = new bootstrap.Modal(document.getElementById('signin-modal'));
                        loginModal.show();

                        // throw کردن خطا برای جلوگیری از ادامه
                        throw new Error('Login required');
                    });
                }
                return response;
            });
        };

        // ========== 3. مدیریت ریدایرکت‌های سرور ==========
        // بررسی پارامتر show_login_modal توی آدرس (برای مواردی که سرور ریدایرکت کرده)
        const urlParams = new URLSearchParams(window.location.search);
        const showLoginModal = urlParams.get('show_login_modal');
        const nextUrl = urlParams.get('next');

        if (showLoginModal === 'true' && nextUrl) {
            sessionStorage.setItem('redirectAfterLogin', nextUrl);
            const loginModal = new bootstrap.Modal(document.getElementById('signin-modal'));
            loginModal.show();

            // پاک کردن پارامتر از آدرس
            const newUrl = window.location.pathname;
            window.history.replaceState({}, document.title, newUrl);
        }
    });