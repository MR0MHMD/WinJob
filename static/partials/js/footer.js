(function () {
    'use strict';

    function getUserRole() {
        // حذف فضاهای خالی احتمالی
        return (document.body.dataset.userRole || 'guest').trim();
    }

    function setupBottomSheets() {
        const role = getUserRole();

        if (role === 'advertiser') {
            const financialBtn = document.getElementById('financialNavBtn');
            const sheet = document.getElementById('financialSheet');
            if (!financialBtn || !sheet) return;

            const closeBtn = sheet.querySelector('#closeFinancialSheet');
            const overlay = sheet.querySelector('.bottom-sheet-overlay');

            function openSheet(e) {
                if (e) e.preventDefault();
                sheet.classList.add('open');
                document.body.style.overflow = 'hidden';
            }

            function closeSheet() {
                sheet.classList.remove('open');
                document.body.style.overflow = '';
            }

            financialBtn.removeEventListener('click', openSheet);
            financialBtn.addEventListener('click', openSheet);
            if (closeBtn) closeBtn.addEventListener('click', closeSheet);
            if (overlay) overlay.addEventListener('click', closeSheet);

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && sheet.classList.contains('open')) closeSheet();
            });

            const sheetContent = sheet.querySelector('.bottom-sheet-content');
            let startY = 0;
            if (sheetContent) {
                sheetContent.addEventListener('touchstart', function (e) {
                    startY = e.touches[0].clientY;
                }, {passive: true});
                sheetContent.addEventListener('touchmove', function (e) {
                    const diff = e.touches[0].clientY - startY;
                    if (diff > 50 && sheetContent.scrollTop === 0) closeSheet();
                }, {passive: true});
            }
        } else if (role === 'influencer') {
            const financialBtn = document.getElementById('financialNavBtnInfluencer');
            const sheet = document.getElementById('financialSheetInfluencer');
            if (!financialBtn || !sheet) return;

            const closeBtn = sheet.querySelector('#closeFinancialSheetInfluencer');
            const overlay = sheet.querySelector('.bottom-sheet-overlay');

            function openSheet(e) {
                if (e) e.preventDefault();
                sheet.classList.add('open');
                document.body.style.overflow = 'hidden';
            }

            function closeSheet() {
                sheet.classList.remove('open');
                document.body.style.overflow = '';
            }

            financialBtn.removeEventListener('click', openSheet);
            financialBtn.addEventListener('click', openSheet);
            if (closeBtn) closeBtn.addEventListener('click', closeSheet);
            if (overlay) overlay.addEventListener('click', closeSheet);

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && sheet.classList.contains('open')) closeSheet();
            });

            const sheetContent = sheet.querySelector('.bottom-sheet-content');
            let startY = 0;
            if (sheetContent) {
                sheetContent.addEventListener('touchstart', function (e) {
                    startY = e.touches[0].clientY;
                }, {passive: true});
                sheetContent.addEventListener('touchmove', function (e) {
                    const diff = e.touches[0].clientY - startY;
                    if (diff > 50 && sheetContent.scrollTop === 0) closeSheet();
                }, {passive: true});
            }
        } else if (role === 'team_member') {
            const financialBtn = document.getElementById('financialNavBtnTeam');
            const sheet = document.getElementById('financialSheetTeam');
            if (!financialBtn || !sheet) return;

            const closeBtn = sheet.querySelector('#closeFinancialSheetTeam');
            const overlay = sheet.querySelector('.bottom-sheet-overlay');

            function openSheet(e) {
                if (e) e.preventDefault();
                sheet.classList.add('open');
                document.body.style.overflow = 'hidden';
            }

            function closeSheet() {
                sheet.classList.remove('open');
                document.body.style.overflow = '';
            }

            financialBtn.removeEventListener('click', openSheet);
            financialBtn.addEventListener('click', openSheet);
            if (closeBtn) closeBtn.addEventListener('click', closeSheet);
            if (overlay) overlay.addEventListener('click', closeSheet);

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && sheet.classList.contains('open')) closeSheet();
            });

            const sheetContent = sheet.querySelector('.bottom-sheet-content');
            let startY = 0;
            if (sheetContent) {
                sheetContent.addEventListener('touchstart', function (e) {
                    startY = e.touches[0].clientY;
                }, {passive: true});
                sheetContent.addEventListener('touchmove', function (e) {
                    const diff = e.touches[0].clientY - startY;
                    if (diff > 50 && sheetContent.scrollTop === 0) closeSheet();
                }, {passive: true});
            }
        } else if (role === 'admin' || role === 'user') {
            // ========== شیت مالی برای ادمین (یا کاربر بدون نقش) ==========
            const financialBtn = document.getElementById('financialNavBtnAdmin');
            const sheet = document.getElementById('financialSheetAdmin');
            if (!financialBtn || !sheet) return;

            const closeBtn = sheet.querySelector('#closeFinancialSheetAdmin');
            const overlay = sheet.querySelector('.bottom-sheet-overlay');

            // دکمه مالی ممکنه وجود نداشته باشه، پس باگ نزنیم
            if (financialBtn) {
                function openSheet(e) {
                    if (e) e.preventDefault();
                    sheet.classList.add('open');
                    document.body.style.overflow = 'hidden';
                }

                function closeSheet() {
                    sheet.classList.remove('open');
                    document.body.style.overflow = '';
                }

                financialBtn.removeEventListener('click', openSheet);
                financialBtn.addEventListener('click', openSheet);
                if (closeBtn) closeBtn.addEventListener('click', closeSheet);
                if (overlay) overlay.addEventListener('click', closeSheet);

                document.addEventListener('keydown', function (e) {
                    if (e.key === 'Escape' && sheet.classList.contains('open')) closeSheet();
                });

                const sheetContent = sheet.querySelector('.bottom-sheet-content');
                let startY = 0;
                if (sheetContent) {
                    sheetContent.addEventListener('touchstart', function (e) {
                        startY = e.touches[0].clientY;
                    }, {passive: true});
                    sheetContent.addEventListener('touchmove', function (e) {
                        const diff = e.touches[0].clientY - startY;
                        if (diff > 50 && sheetContent.scrollTop === 0) closeSheet();
                    }, {passive: true});
                }
            }
        }
    }

    function setActiveNavItem() {
        const role = getUserRole();
        const currentPath = window.location.pathname;

        if (role === 'advertiser') {
            const items = document.querySelectorAll('.bottom-nav-item');
            items.forEach(item => item.classList.remove('active'));

            let activeNav = null;
            if (currentPath === '/' || currentPath.startsWith('/advertisers/dashboard') || currentPath.startsWith('/influencers/dashboard') || currentPath.startsWith('/content_team/dashboard')) {
                activeNav = 'خانه';
            } else if (currentPath.startsWith('/advertisers/my_campaigns') || currentPath.includes('/advertisers/campaign_detail')) {
                activeNav = 'تبلیغات';
            } else if (currentPath.startsWith('/accounts/wallet')) {
                activeNav = 'مالی';
            } else if (currentPath.startsWith('/campaigns/campaign_create_step')) {
                activeNav = 'ساخت تبلیغ';
            } else if (currentPath.startsWith('/tickets')) {
                activeNav = 'پشتیبانی';
            }

            if (activeNav) {
                items.forEach(item => {
                    const label = item.querySelector('.bottom-nav-label');
                    if (label && label.innerText.trim() === activeNav) {
                        item.classList.add('active');
                    }
                });
            }
        } else if (role === 'influencer') {
            const navContainer = document.getElementById('influencerBottomNav');
            if (!navContainer) return;
            const items = navContainer.querySelectorAll('.bottom-nav-item');
            items.forEach(item => item.classList.remove('active'));

            let activeNav = null;
            if (currentPath === '/' || currentPath.startsWith('/influencers/dashboard')) {
                activeNav = 'خانه';
            } else if (currentPath.startsWith('/influencers/order_list') || currentPath.includes('/influencers/order_detail')) {
                activeNav = 'سفارشات';
            } else if (currentPath.startsWith('/influencers/my_channels') || currentPath.includes('/influencers/my_channels/edit') || currentPath.includes('/influencers/channels/')) {
                activeNav = 'کانال‌ها';
            } else if (currentPath.startsWith('/accounts/wallet') || currentPath.startsWith('/influencers/coupons')) {
                activeNav = 'مالی';
            } else if (currentPath.startsWith('/tickets')) {
                activeNav = 'پشتیبانی';
            }

            if (activeNav) {
                items.forEach(item => {
                    const label = item.querySelector('.bottom-nav-label');
                    if (label && label.innerText.trim() === activeNav) {
                        item.classList.add('active');
                    }
                });
            }
        } else if (role === 'team_member') {
            const navContainer = document.getElementById('teamBottomNav');
            if (!navContainer) return;
            const items = navContainer.querySelectorAll('.bottom-nav-item');
            items.forEach(item => item.classList.remove('active'));

            let activeNav = null;
            if (currentPath === '/' || currentPath.startsWith('/content_team/dashboard')) {
                activeNav = 'خانه';
            } else if (currentPath.startsWith('/content_team/team/orders')) {
                activeNav = 'سفارشات';
            } else if (currentPath.startsWith('/content_team/plans/management')) {
                activeNav = 'پلن‌ها';
            } else if (currentPath.startsWith('/content_team/team/manage') || currentPath.includes('/members/manage/')) {
                activeNav = 'مدیریت تیم';
            } else if (currentPath.startsWith('/accounts/wallet') || currentPath.startsWith('/content_team/team/coupons') || currentPath.startsWith('/accounts/wallet/deposit')) {
                activeNav = 'مالی';
            } else if (currentPath.startsWith('/tickets')) {
                activeNav = 'پشتیبانی';
            }

            if (activeNav) {
                items.forEach(item => {
                    const label = item.querySelector('.bottom-nav-label');
                    if (label && label.innerText.trim() === activeNav) {
                        item.classList.add('active');
                    }
                });
            }
        } else if (role === 'admin' || role === 'user') {
            // ========== هایلایت ناوبری ادمین ==========
            const navContainer = document.getElementById('adminBottomNav');
            if (!navContainer) return;
            const items = navContainer.querySelectorAll('.bottom-nav-item');
            items.forEach(item => item.classList.remove('active'));

            let activeNav = null;
            if (currentPath === '/support/' || currentPath.startsWith('/support/dashboard')) {
                activeNav = 'داشبورد';
            } else if (currentPath.startsWith('/support/users')) {
                activeNav = 'کاربران';
            } else if (currentPath.startsWith('/support/tickets')) {
                activeNav = 'تیکت‌ها';
            } else if (currentPath.startsWith('/support/campaigns')) {
                activeNav = 'کمپین‌ها';
            } else if (currentPath.startsWith('/support/channels')) {
                activeNav = 'کانال‌ها';
            } else if (currentPath.startsWith('/support/reports')) {
                activeNav = 'گزارشات';
            }

            if (activeNav) {
                items.forEach(item => {
                    const label = item.querySelector('.bottom-nav-label');
                    if (label && label.innerText.trim() === activeNav) {
                        item.classList.add('active');
                    }
                });
            }
        }
    }

    const hiddenPaths = [
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

    function handleFooterVisibility() {
        const currentPath = window.location.pathname;
        const footer = document.querySelector('.footer');
        const bottomNav = document.querySelector('.bottom-nav');
        const shouldHide = hiddenPaths.some(p => currentPath.includes(p));

        if (footer) footer.style.display = shouldHide ? 'none' : '';
        if (bottomNav) bottomNav.style.display = shouldHide ? 'none' : '';
        if (shouldHide) document.body.style.paddingBottom = '0';
    }

    let lastUrl = location.href;

    function observeUrlChanges() {
        new MutationObserver(() => {
            const url = location.href;
            if (url !== lastUrl) {
                lastUrl = url;
                setTimeout(() => {
                    setActiveNavItem();
                    handleFooterVisibility();
                    setupBottomSheets();
                }, 100);
            }
        }).observe(document, {subtree: true, childList: true});
    }

    function init() {
        console.log('User role detected:', getUserRole()); // برای دیباگ - در تولید حذف شود
        setupBottomSheets();
        setActiveNavItem();
        handleFooterVisibility();
        observeUrlChanges();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();