(function () {
    // منتظر میمونیم تا صفحه کامل بارگذاری بشه
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFinancialSheet);
    } else {
        initFinancialSheet();
    }

    function initFinancialSheet() {
        const bottomSheet = document.getElementById('financialSheet');
        const closeBtn = document.getElementById('closeFinancialSheet');
        const financialBtn = document.getElementById('financialNavBtn');
        const overlay = document.querySelector('.bottom-sheet-overlay');

        // اگه المنت‌ها وجود ندارن، خارج شو
        if (!bottomSheet) return;

        // باز کردن پنل
        function openBottomSheet() {
            bottomSheet.classList.add('open');
            document.body.style.overflow = 'hidden';
        }

        // بستن پنل
        function closeBottomSheet() {
            bottomSheet.classList.remove('open');
            document.body.style.overflow = '';
        }

        // رویداد کلیک روی دکمه مالی
        if (financialBtn) {
            financialBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                openBottomSheet();
            });
        }

        // بستن با دکمه close
        if (closeBtn) {
            closeBtn.addEventListener('click', closeBottomSheet);
        }

        // بستن با کلیک روی لایه پشت پنل
        if (overlay) {
            overlay.addEventListener('click', closeBottomSheet);
        }

        // بستن با دکمه Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && bottomSheet.classList.contains('open')) {
                closeBottomSheet();
            }
        });

        // گزینه‌های داخل پنل
        const options = document.querySelectorAll('.financial-option');
        options.forEach(option => {
            option.addEventListener('click', function () {
                const optionType = this.getAttribute('data-option');
                console.log('کلیک روی گزینه:', optionType);
                // اینجا میتونی بعداً کارهای مختلف انجام بدی
                // فعلاً پنل رو میبندیم (اختیاری)
                // closeBottomSheet();
            });
        });

        // قابلیت کشیدن به پایین برای بستن در موبایل
        let startY = 0;
        const sheetContent = document.querySelector('.bottom-sheet-content');

        if (sheetContent) {
            sheetContent.addEventListener('touchstart', function (e) {
                startY = e.touches[0].clientY;
            }, {passive: true});

            sheetContent.addEventListener('touchmove', function (e) {
                const currentY = e.touches[0].clientY;
                const diff = currentY - startY;

                if (diff > 50 && sheetContent.scrollTop === 0) {
                    closeBottomSheet();
                }
            }, {passive: true});
        }
    }
})();

(function () {
    'use strict';

    const routes = {
        home: [
            '/',
            '/advertisers/dashboard/',
            '/influencers/dashboard/',
            '/content_team/dashboard/'
        ],
        ads: [
            '/advertisers/my_campaigns'
        ],
        finance: [
            '/accounts/wallet/',
            '/accounts/wallet/deposit/'
        ]
    };

    function setActiveNavItem() {
        const currentPath = window.location.pathname;
        const navItems = document.querySelectorAll('.bottom-nav-item');

        if (!navItems.length) return;

        // حذف کلاس active از همه
        navItems.forEach(item => item.classList.remove('active'));

        let activeSection = null;

        // تشخیص بر اساس مسیرها
        if (routes.home.some(path => currentPath === path ||
            (path !== '/' && currentPath.startsWith(path)))) {
            activeSection = 'خانه';
        } else if (routes.ads.some(path => currentPath.startsWith(path))) {
            activeSection = 'تبلیغات';
        } else if (currentPath.includes('/advertisers/campaign_detail/')) {
            activeSection = 'تبلیغات';
        } else if (routes.finance.some(path => currentPath.startsWith(path))) {
            activeSection = 'مالی';
        } else if (currentPath.includes('/create-ad/')) {
            activeSection = 'ساخت تبلیغ';
        } else if (currentPath.includes('/support/')) {
            activeSection = 'پشتیبانی';
        }

        // اعمال کلاس active
        if (activeSection) {
            navItems.forEach(item => {
                const label = item.querySelector('.bottom-nav-label');
                if (label && label.innerText === activeSection) {
                    item.classList.add('active');
                }
            });
        }

        // لاگ برای دیباگ (حذف در محیط تولید)
        if (window.location.hostname === 'localhost') {
            console.log('[Nav] Path:', currentPath, '-> Active:', activeSection);
        }
    }

    // مدیریت پنل مالی
    function initFinancialPanel() {
        const bottomSheet = document.getElementById('financialSheet');
        const financialBtn = document.getElementById('financialNavBtn');

        if (!bottomSheet || !financialBtn) return;

        // نظارت بر باز و بسته شدن پنل
        const observer = new MutationObserver(() => {
            if (bottomSheet.classList.contains('open')) {
                financialBtn.classList.add('active');
            } else {
                // چک کنیم کاربر توی صفحه مالی هست یا نه
                if (!window.location.pathname.includes('/accounts/wallet/')) {
                    financialBtn.classList.remove('active');
                }
            }
        });

        observer.observe(bottomSheet, {attributes: true, attributeFilter: ['class']});
    }

    // اجرا در زمان مناسب
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setActiveNavItem();
            initFinancialPanel();
        });
    } else {
        setActiveNavItem();
        initFinancialPanel();
    }

    // برای تغییرات URL (SPA, Turbo, HTMX)
    const observeUrlChanges = () => {
        let lastUrl = location.href;
        new MutationObserver(() => {
            const url = location.href;
            if (url !== lastUrl) {
                lastUrl = url;
                setTimeout(setActiveNavItem, 50);
            }
        }).observe(document, {subtree: true, childList: true});
    };

    observeUrlChanges();
})();

const hiddenFooterPaths = [
    '/campaigns/campaign_create_step1',
    '/campaigns/campaign_create_step2',
    '/campaigns/campaign_create_step3',
    '/campaigns/campaign_create_step3/ready',
    '/campaigns/campaign_create_step3/team',
    '/campaigns/campaign_create_step4',
    '/accounts/login',
    '/accounts/register',
    '/accounts/verify-otp/',
    '/pending'
];

function checkAndHideFooter() {
    const currentPath = window.location.pathname;
    const footerElement = document.querySelector('.footer');
    const bottomNav = document.querySelector('.bottom-nav');

    // چک کن که آیا مسیر فعلی توی لیست هست یا نه
    const shouldHide = hiddenFooterPaths.some(path => currentPath.includes(path));

    if (shouldHide) {
        if (footerElement) footerElement.style.display = 'none';
        if (bottomNav) bottomNav.style.display = 'none';
        // همچنین padding-bottom بدنه رو ریست کن
        document.body.style.paddingBottom = '0';
    } else {
        if (footerElement) footerElement.style.display = '';
        if (bottomNav) bottomNav.style.display = '';
    }
}

// اجرا هنگام بارگذاری
document.addEventListener('DOMContentLoaded', checkAndHideFooter);

// اجرا هنگام تغییر مسیر (برای SPA یا Turbo)
const observeUrlChanges = () => {
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            setTimeout(checkAndHideFooter, 50);
        }
    }).observe(document, { subtree: true, childList: true });
};

observeUrlChanges();