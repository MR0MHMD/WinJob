// campaigns/static/campaigns/js/create_step_2/create_step_2.js

(function () {
    'use strict';

    const PRICES = window.RATES_PRICES || {};
    const PREV_SELECTED = window.PREV_SELECTED_RATE_IDS || [];
    const CAMPAIGN_ID = window.CAMPAIGN_ID || null;
    const IS_REPLACEMENT_MODE = window.IS_REPLACEMENT_MODE || false;
    const WALLET_BALANCE = window.WALLET_BALANCE || 0;

    // ========== در حالت جایگزینی، لیست انتخاب‌ها رو خالی شروع کن ==========
    // دیگر از PREV_SELECTED برای مقداردهی اولیه استفاده نمیکنیم
    let memorySelectedIds = [];

    // ========== کلید localStorage برای حالت عادی ==========
    const STORAGE_KEY = CAMPAIGN_ID ? 'selected_rates_' + CAMPAIGN_ID : 'selected_rates_temp';

    const totalPriceEl = document.getElementById('total-price-display');
    const summaryBar = document.getElementById('price-summary-bar');
    const countEl = document.getElementById('selected-count');
    const breakdownEl = document.getElementById('price-breakdown');
    const CALCULATE_URL = window.CALCULATE_URL || "/campaigns/campaign_create_step2/calculate";

    let debounceTimer = null;
    let initialLoadDone = false;

    // ========== توابع کمکی ==========
    function toPersianNum(num) {
        return String(num).replace(/\d/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[d];
        });
    }

    function formatPrice(num) {
        return toPersianNum(num.toLocaleString('en-US')) + ' تومان';
    }

    // ========== دریافت لیست انتخاب‌ها ==========
    function getStoredIds() {
        if (IS_REPLACEMENT_MODE) {
            // ========== در حالت جایگزینی، از حافظه استفاده کن ==========
            return memorySelectedIds.slice();
        }

        // ========== حالت عادی: از localStorage ==========
        if (!CAMPAIGN_ID) return [];
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                return JSON.parse(stored);
            } catch (e) {
                return [];
            }
        }
        return [];
    }

    // ========== ذخیره لیست انتخاب‌ها ==========
    function setStoredIds(ids) {
        if (IS_REPLACEMENT_MODE) {
            // ========== در حالت جایگزینی، فقط حافظه رو آپدیت کن ==========
            memorySelectedIds = ids.slice();
            return;
        }

        // ========== حالت عادی: ذخیره در localStorage ==========
        if (!CAMPAIGN_ID) return;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    }

    // ========== اضافه کردن ID ==========
    function addId(id) {
        const ids = getStoredIds();
        if (!ids.includes(id)) {
            ids.push(id);
            setStoredIds(ids);
        }
        syncHiddenFields();
        updateUIFromStored();
    }

    // ========== حذف ID ==========
    function removeId(id) {
        const ids = getStoredIds();
        const index = ids.indexOf(id);
        if (index !== -1) {
            ids.splice(index, 1);
            setStoredIds(ids);
        }
        syncHiddenFields();
        updateUIFromStored();
    }

    // ========== همگام‌سازی فیلدهای مخفی ==========
    function syncHiddenFields() {
        const container = document.getElementById('hidden-selected-container');
        if (!container) return;

        container.innerHTML = '';

        const ids = getStoredIds();
        ids.forEach(function (id) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'rates';
            input.value = id;
            container.appendChild(input);
        });
    }

    // ========== به‌روزرسانی UI ==========
    function updateUIFromStored() {
        const ids = getStoredIds();
        const count = ids.length;
        countEl.textContent = toPersianNum(count);
        summaryBar.classList.toggle('has-selection', count > 0);

        const total = ids.reduce(function (sum, id) {
            return sum + (PRICES[String(id)] || 0);
        }, 0);
        totalPriceEl.textContent = formatPrice(total);

        // به‌روزرسانی وضعیت کیف پول
        updateWalletStatus(ids);

        if (count > 0) {
            fetchAccuratePrice(ids);
        } else {
            totalPriceEl.classList.remove('updating');
            breakdownEl.innerHTML = '';
        }
    }

    // ========== دریافت قیمت دقیق از سرور ==========
    function fetchAccuratePrice(selectedIds) {
        if (!selectedIds.length) {
            totalPriceEl.classList.remove('updating');
            breakdownEl.innerHTML = '';
            return;
        }

        totalPriceEl.classList.add('updating');

        fetch(CALCULATE_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({service_rate_ids: selectedIds}),
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                totalPriceEl.classList.remove('updating');
                if (data.error) return;
                totalPriceEl.textContent = formatPrice(data.total);

                if (data.breakdown && data.breakdown.length) {
                    const totalCount = data.breakdown.length;
                    const displayItems = data.breakdown.slice(0, 4);
                    const remainingCount = totalCount - 4;

                    let namesHtml = '';
                    displayItems.forEach(function (item) {
                        namesHtml += '<span class="d-block">' +
                            '<span class="text-light">' + item.name + '</span>' +
                            ' · ' +
                            '<span style="color:#a5b4fc;">' + toPersianNum(item.formatted) + ' تومان</span>' +
                            '</span>';
                    });
                    if (remainingCount > 0) {
                        namesHtml += '<span class="d-block text-muted small mt-1" style="color:#a5b4fc;">و ' +
                            toPersianNum(remainingCount) + ' نفر دیگر</span>';
                    }
                    breakdownEl.innerHTML = namesHtml;
                } else {
                    breakdownEl.innerHTML = '';
                }
            })
            .catch(function () {
                totalPriceEl.classList.remove('updating');
            });
    }

    // ========== محاسبه مجموع قیمت ==========
    function calculateTotalPrice(ids) {
        let total = 0;
        ids.forEach(function (id) {
            total += (PRICES[String(id)] || 0);
        });
        return total;
    }

    // ========== بررسی محدودیت کیف پول ==========
    function validateWalletLimit(ids) {
        if (!IS_REPLACEMENT_MODE) return true;
        const total = calculateTotalPrice(ids);
        if (total > WALLET_BALANCE) {
            const formattedTotal = total.toLocaleString('en-US');
            const formattedBalance = WALLET_BALANCE.toLocaleString('en-US');
            if (typeof showNotificationModal !== 'undefined') {
                showNotificationModal(
                    '⚠️ محدودیت کیف پول',
                    `مجموع قیمت کانال‌های انتخاب شده (${formattedTotal} تومان) از موجودی کیف پول شما (${formattedBalance} تومان) بیشتر است.`,
                    'warning'
                );
            }
            return false;
        }
        return true;
    }

    // ========== به‌روزرسانی نمایش وضعیت کیف پول ==========
    function updateWalletStatus(ids) {
        if (!IS_REPLACEMENT_MODE) return;
        const total = calculateTotalPrice(ids);
        const remaining = WALLET_BALANCE - total;

        const walletStatusEl = document.getElementById('wallet-status-display');
        if (walletStatusEl) {
            if (remaining >= 0) {
                walletStatusEl.innerHTML = `
                    <span class="text-success">✅ موجودی باقی‌مانده: ${remaining.toLocaleString('en-US')} تومان</span>
                `;
            } else {
                walletStatusEl.innerHTML = `
                    <span class="text-danger">❌ مجموع قیمت از موجودی کیف پول بیشتر است!</span>
                `;
            }
        }
    }

    // ========== مدیریت کلیک روی کارت ==========
    function handleCardClick(wrapper) {
        const id = parseInt(wrapper.dataset.id);
        const checkbox = document.querySelector('#rate_' + id);
        if (!checkbox) return;

        const cardInner = wrapper.querySelector('.influencer-card-inner');
        const isCurrentlyChecked = checkbox.checked;

        // شبیه‌سازی تغییر وضعیت
        let tempIds = getStoredIds().slice();
        if (isCurrentlyChecked) {
            const index = tempIds.indexOf(id);
            if (index !== -1) tempIds.splice(index, 1);
        } else {
            tempIds.push(id);
        }

        // ========== اعتبارسنجی محدودیت کیف پول ==========
        if (!validateWalletLimit(tempIds)) {
            return;
        }

        // اعمال تغییر
        if (isCurrentlyChecked) {
            checkbox.checked = false;
            cardInner.classList.remove('selected');
            removeId(id);
        } else {
            checkbox.checked = true;
            cardInner.classList.add('selected');
            addId(id);
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            const currentIds = getStoredIds();
            if (currentIds.length > 0) {
                fetchAccuratePrice(currentIds);
            }
        }, 400);
    }

    // ========== بازیابی انتخاب‌های قبلی ==========
    function restoreSelection() {
        let storedIds = getStoredIds();

        document.querySelectorAll('.influencer-card-wrapper').forEach(function (wrapper) {
            const id = parseInt(wrapper.dataset.id);
            const checkbox = document.querySelector('#rate_' + id);
            const cardInner = wrapper.querySelector('.influencer-card-inner');

            // ========== در حالت جایگزینی، هیچ کانالی نباید از قبل انتخاب شده باشه ==========
            // مگر اینکه کاربر قبلاً انتخاب کرده باشه (که توی memorySelectedIds ذخیره شده)
            if (checkbox && storedIds.includes(id)) {
                checkbox.checked = true;
                cardInner.classList.add('selected');
            } else if (checkbox) {
                checkbox.checked = false;
                cardInner.classList.remove('selected');
            }
        });

        updateUIFromStored();
        syncHiddenFields();
        initialLoadDone = true;
    }

    // ========== آماده‌سازی فرم برای ارسال ==========
    function prepareFormForSubmit() {
        syncHiddenFields();

        document.querySelectorAll('.influencer-checkbox').forEach(function (cb) {
            cb.disabled = true;
        });
    }

    // ========== رویدادها ==========
    document.querySelectorAll('.influencer-card-wrapper').forEach(function (wrapper) {
        wrapper.addEventListener('click', function (e) {
            e.stopPropagation();
            handleCardClick(wrapper);
        });
    });

    // ========== دریافت CSRF Token ==========
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach(function (cookie) {
                const c = cookie.trim();
                if (c.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(c.slice(name.length + 1));
                }
            });
        }
        return cookieValue;
    }

    // ========== مدیریت پارامتر select_rate ==========
    function handleSelectRateParam() {
        const urlParams = new URLSearchParams(window.location.search);
        const selectRate = urlParams.get('select_rate');
        if (!selectRate) return;

        urlParams.delete('select_rate');
        const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
        window.history.replaceState({}, '', newUrl);

        const rateId = parseInt(selectRate, 10);
        if (isNaN(rateId)) return;

        let stored = getStoredIds();
        if (!stored.includes(rateId)) {
            stored.push(rateId);
            setStoredIds(stored);
            if (typeof showNotificationModal !== 'undefined') {
                showNotificationModal('موفق', 'ناشر مورد نظر با موفقیت انتخاب شد.', 'success');
            }
        }
    }

    // ========== اجرا ==========
    handleSelectRateParam();
    restoreSelection();

    // ========== رویداد submit فرم ==========
    const step2Form = document.getElementById('step2-form');
    if (step2Form) {
        step2Form.addEventListener('submit', function () {
            prepareFormForSubmit();
        });
    }

})();