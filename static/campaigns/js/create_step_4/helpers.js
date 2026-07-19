function showDiscountMessage(text, type) {
    const feedbackDiv = document.getElementById('discount-feedback');
    if (!feedbackDiv) return;

    feedbackDiv.textContent = text;
    feedbackDiv.className = 'discount-message ' + (type === 'success' ? 'discount-success' : 'discount-error');
    feedbackDiv.classList.remove('d-none');

    setTimeout(() => feedbackDiv.classList.add('d-none'), 5000);
}

function addAppliedBadge(scope, code, scopeMeta) {
    const appliedList = document.getElementById('applied-discounts-list');
    if (!appliedList) return;

    if (appliedList.querySelector(`[data-scope="${scope}"]`)) return;

    const badgeDiv = document.createElement('div');
    badgeDiv.className = 'applied-discount-badge';
    badgeDiv.setAttribute('data-scope', scope);
    badgeDiv.innerHTML = `
        <i>${scopeMeta[scope].icon}</i>
        <span>${scopeMeta[scope].label}: <strong>${code}</strong></span>
        <span class="applied-success-icon">✓</span>
    `;
    appliedList.appendChild(badgeDiv);
}

function checkAndDisableUniDiscount(appliedScopes, uniInput, uniBtn) {
    const allApplied = Object.values(appliedScopes).every(v => v === true);
    if (allApplied) {
        uniInput.disabled = true;
        uniBtn.disabled = true;
        uniBtn.textContent = 'همه تخفیف‌ها اعمال شد';
        uniBtn.classList.add('disabled');
        showDiscountMessage('شما از هر سه نوع تخفیف (اینفلوئنسر، تیم محتوا، پلتفرم) استفاده کرده‌اید.', 'info');
    } else {
        uniInput.disabled = false;
        uniBtn.disabled = false;
        uniBtn.textContent = 'اعمال تخفیف';
        uniBtn.classList.remove('disabled');
    }
}

function updateTotals(data) {
    const finalDisplay = document.getElementById('final-price-value');
    if (finalDisplay) {
        finalDisplay.innerHTML = data.payable_amount_formatted + ' <span class="final-price-unit">تومان</span>';
    }

    const finalTotalSpan = document.getElementById('final-total-display');
    if (finalTotalSpan) {
        finalTotalSpan.textContent = data.final_total_formatted + ' تومان';
    }

    const payableRow = document.getElementById('payable-row');
    const payableSpan = document.getElementById('payable-amount-display');
    const totalDiscountInfo = document.getElementById('total-discount-info');
    const totalDiscountVal = document.getElementById('total-discount-value');

    if (data.discount_amount > 0) {
        if (payableRow) payableRow.classList.remove('d-none');
        if (payableSpan) payableSpan.textContent = data.payable_amount_formatted + ' تومان';
        if (totalDiscountInfo) totalDiscountInfo.classList.remove('d-none');
        if (totalDiscountVal) totalDiscountVal.textContent = data.discount_amount_formatted;
    } else {
        if (payableRow) payableRow.classList.add('d-none');
        if (totalDiscountInfo) totalDiscountInfo.classList.add('d-none');
    }

    // به‌روزرسانی ردیف‌های تخفیف
    updateDiscountRow('influencer', data);
    updateDiscountRow('content_team', data);
    updateDiscountRow('platform', data);
}

function updateDiscountRow(scope, data) {
    const discountKey = scope + '_discount';
    const discountValue = data.discount_breakdown?.[discountKey] || 0;

    const row = document.getElementById('discount-' + scope + '-row');
    const valSpan = document.getElementById('discount-' + scope + '-value');
    const labelSpan = document.getElementById(scope + '-discount-label');

    if (!row) return;

    if (discountValue > 0 && data.scope === scope) {
        row.classList.remove('d-none');
        if (valSpan) valSpan.textContent = '- ' + discountValue.toLocaleString() + ' تومان';
        if (labelSpan) labelSpan.textContent = '(' + data.coupon_code + ')';
    } else if (discountValue === 0) {
        row.classList.add('d-none');
    }
}