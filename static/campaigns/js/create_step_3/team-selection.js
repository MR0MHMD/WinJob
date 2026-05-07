(function () {
    'use strict';

    const PRICES = window.TEAM_RATES || {};
    const EXISTING_RATE_ID = window.EXISTING_RATE_ID || null;

    const totalPriceEl = document.getElementById('total-price-display');
    const summaryBar = document.getElementById('price-summary-bar');
    const countEl = document.getElementById('selected-count');
    const breakdownEl = document.getElementById('price-breakdown');

    function toPersianNum(num) {
        return String(num).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
    }

    function formatPrice(num) {
        return toPersianNum(num.toLocaleString('en-US')) + ' تومان';
    }

    function getSelectedId() {
        const checked = document.querySelector('.team-radio:checked');
        return checked ? parseInt(checked.value) : null;
    }

    function updatePriceUI() {

        const selectedId = getSelectedId();

        if (!selectedId) {
            summaryBar.classList.remove('has-selection');
            countEl.textContent = toPersianNum(0);
            totalPriceEl.textContent = '۰ تومان';
            breakdownEl.innerHTML = '';
            return;
        }

        const priceData = PRICES[String(selectedId)];
        const minutes = window.CONTENT_MINUTES || null;

        if (!priceData) return;

        summaryBar.classList.add('has-selection');
        countEl.textContent = toPersianNum(1);

        if (minutes && minutes > 0) {

            const pricePerMin = priceData.price / minutes;

            totalPriceEl.textContent = formatPrice(priceData.price);

            breakdownEl.innerHTML =
                `<span class="d-block text-light">${priceData.teamName}</span>
                 <span class="d-block mt-1" style="font-size:0.85rem;">
                 <span style="color:#a5b4fc; display:block">قیمت هر دقیقه: ${formatPrice(pricePerMin)}</span>
                 <span style="color:#a5b4fc; display:block">تعداد دقیقه: ${toPersianNum(minutes)}</span>
                 </span>`;

        } else {

            totalPriceEl.textContent = formatPrice(priceData.price);

            breakdownEl.innerHTML =
                `<span class="d-block">
                    <span class="text-light">${priceData.teamName}</span>
                    ·
                    <span style="color:#a5b4fc;">${formatPrice(priceData.price)}</span>
                </span>`;
        }
    }

    function handleCardClick(wrapper) {

        const id = wrapper.dataset.id;
        const radio = document.querySelector('#rate_' + id);

        if (!radio) return;

        document.querySelectorAll('.team-card-inner')
            .forEach(card => card.classList.remove('selected'));

        radio.checked = true;

        wrapper.querySelector('.team-card-inner')
            .classList.add('selected');

        updatePriceUI();

        document.dispatchEvent(new Event("teamSelected"));
    }

    function restoreSelection() {

        if (!EXISTING_RATE_ID) return;

        const radio = document.querySelector('#rate_' + EXISTING_RATE_ID);

        if (!radio) return;

        radio.checked = true;

        const wrapper = radio.closest('.team-card-wrapper');

        if (wrapper) {
            wrapper.querySelector('.team-card-inner')
                .classList.add('selected');
        }

        updatePriceUI();

        document.dispatchEvent(new Event("teamSelected"));
    }

    window.initTeamSelection = function () {

        document.querySelectorAll('.team-card-wrapper')
            .forEach(wrapper => {
                wrapper.addEventListener('click', () => handleCardClick(wrapper));
            });

        restoreSelection();
    };

})();
