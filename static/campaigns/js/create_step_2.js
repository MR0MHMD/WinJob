(function () {
    'use strict';
    var PRICES = window.RATES_PRICES || {};
    var PREV_SELECTED = window.PREV_SELECTED_RATE_IDS || [];

    var totalPriceEl = document.getElementById('total-price-display');
    var summaryBar = document.getElementById('price-summary-bar');
    var countEl = document.getElementById('selected-count');
    var breakdownEl = document.getElementById('price-breakdown');

    // باید با ویوی calculate همخوانی داشته باشه
    var CALCULATE_URL = window.CALCULATE_URL || "/campaigns/campaign_create_step2/calculate";

    var debounceTimer = null;

    function toPersianNum(num) {
        return String(num).replace(/\d/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[d];
        });
    }

    function formatPrice(num) {
        return toPersianNum(num.toLocaleString('en-US')) + ' تومان';
    }

    function getSelectedIds() {
        return Array.from(
            document.querySelectorAll('.influencer-checkbox:checked')
        ).map(function (cb) {
            return parseInt(cb.value);
        });
    }

    function updateUIInstant(selectedIds) {
        countEl.textContent = toPersianNum(selectedIds.length);

        summaryBar.classList.toggle('has-selection', selectedIds.length > 0);

        var instant = selectedIds.reduce(function (sum, id) {
            return sum + (PRICES[String(id)] || 0);
        }, 0);

        totalPriceEl.textContent = formatPrice(instant);
    }

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
            // این کلید باید با backend شما یکی باشه
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
                    var html = data.breakdown.map(function (item) {
                        return '<span class="d-block">' +
                            '<span class="text-light">' + item.name + '</span>' +
                            ' · ' +
                            '<span style="color:#a5b4fc;">' + toPersianNum(item.formatted) + ' تومان</span>' +
                            '</span>';
                    }).join('');
                    breakdownEl.innerHTML = html;
                } else {
                    breakdownEl.innerHTML = '';
                }
            })
            .catch(function () {
                totalPriceEl.classList.remove('updating');
            });
    }

    function handleCardClick(wrapper) {
        var id = wrapper.dataset.id;

        var checkbox = document.querySelector('#rate_' + id);
        if (!checkbox) return;

        var cardInner = wrapper.querySelector('.influencer-card-inner');

        checkbox.checked = !checkbox.checked;
        cardInner.classList.toggle('selected', checkbox.checked);

        var selectedIds = getSelectedIds();
        updateUIInstant(selectedIds);

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            fetchAccuratePrice(selectedIds);
        }, 400);
    }

    function restoreSelection() {
        PREV_SELECTED.forEach(function (id) {
            var wrapper = document.querySelector('[data-id="' + id + '"]');
            if (!wrapper) return;

            var checkbox = document.querySelector('#rate_' + id);
            var cardInner = wrapper.querySelector('.influencer-card-inner');

            if (checkbox) {
                checkbox.checked = true;
                cardInner.classList.add('selected');
            }
        });

        var selectedIds = getSelectedIds();
        if (selectedIds.length) {
            updateUIInstant(selectedIds);
            fetchAccuratePrice(selectedIds);
        }
    }

    document.querySelectorAll('.influencer-card-wrapper').forEach(function (wrapper) {
        wrapper.addEventListener('click', function () {
            handleCardClick(wrapper);
        });
    });

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach(function (cookie) {
                var c = cookie.trim();
                if (c.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(c.slice(name.length + 1));
                }
            });
        }
        return cookieValue;
    }

    restoreSelection();
})();
