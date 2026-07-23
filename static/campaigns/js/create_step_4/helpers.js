// campaigns/static/campaigns/js/create_step_4/helpers.js

function formatNumber(num) {
    if (!num && num !== 0) return '۰';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function showDiscountMessage(text, type) {
    const feedbackDiv = document.getElementById('discount-feedback');
    if (!feedbackDiv) return;

    feedbackDiv.textContent = text;
    feedbackDiv.className = 'discount-message mt-2 ' + (type === 'success' ? 'discount-success' : 'discount-error');
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
        showDiscountMessage('شما از هر سه نوع تخفیف استفاده کرده‌اید.', 'info');
    } else {
        uniInput.disabled = false;
        uniBtn.disabled = false;
        uniBtn.textContent = 'اعمال تخفیف';
    }
}

// ============================================================
// تابع آپدیت کامل UI با پشتیبانی از شناسه‌های تکراری
// ============================================================
function updateTotals(data) {
    // ---------------------------------------------------------
    // 1. هزینه ناشران
    // ---------------------------------------------------------
    const influencerFinal = document.getElementById('influencer-final-display');
    if (influencerFinal && data.influencer_cost !== undefined) {
        influencerFinal.textContent = `${formatNumber(data.influencer_cost)} تومان`;
    }

    const influencerBase = document.getElementById('influencer-base-display');
    if (influencerBase && data.base_influencer_cost !== undefined) {
        const influencerRow = influencerBase.closest('.cost-row');
        const influencerDiscountLabel = influencerRow?.querySelector('.d-flex.flex-column')?.querySelector('span.text-success.ms-1');

        if (data.influencer_discount_amount > 0) {
            influencerBase.innerHTML = `<span class="text-decoration-line-through text-danger">${formatNumber(data.base_influencer_cost)} تومان</span>`;
            influencerBase.classList.remove('d-none');
            if (influencerDiscountLabel) {
                influencerDiscountLabel.textContent = `تخفیف: ${formatNumber(data.influencer_discount_amount)} تومان`;
                influencerDiscountLabel.classList.remove('d-none');
            }
        } else {
            influencerBase.innerHTML = '';
            influencerBase.classList.add('d-none');
            if (influencerDiscountLabel) {
                influencerDiscountLabel.classList.add('d-none');
            }
        }
    }

    // ---------------------------------------------------------
    // 2. هزینه تیم محتوا
    // ---------------------------------------------------------
    const contentFinal = document.getElementById('content-final-display');
    if (contentFinal && data.content_cost !== undefined) {
        contentFinal.textContent = `${formatNumber(data.content_cost)} تومان`;
    }

    const contentBase = document.getElementById('content-base-display');
    if (contentBase && data.base_content_cost !== undefined) {
        const contentRow = contentBase.closest('.cost-row');
        const contentDiscountLabel = contentRow?.querySelector('.d-flex.flex-column')?.querySelector('span.text-success.ms-1');

        if (data.content_discount_amount > 0) {
            contentBase.innerHTML = `<span class="text-decoration-line-through text-danger">${formatNumber(data.base_content_cost)} تومان</span>`;
            contentBase.classList.remove('d-none');
            if (contentDiscountLabel) {
                contentDiscountLabel.textContent = `تخفیف: ${formatNumber(data.content_discount_amount)} تومان`;
                contentDiscountLabel.classList.remove('d-none');
            }
        } else {
            contentBase.innerHTML = '';
            contentBase.classList.add('d-none');
            if (contentDiscountLabel) {
                contentDiscountLabel.classList.add('d-none');
            }
        }
    }

    // ---------------------------------------------------------
    // 3. کمیسیون پلتفرم
    // ---------------------------------------------------------
    const commissionFinal = document.getElementById('commission-final-display');
    if (commissionFinal && data.commission !== undefined) {
        commissionFinal.textContent = `+ ${formatNumber(data.commission)} تومان`;
    }

    const commissionBase = document.getElementById('commission-base-display');
    if (commissionBase && data.base_commission !== undefined) {
        const commissionRow = commissionBase.closest('.cost-row');
        const commissionDiscountLabel = commissionRow?.querySelector('.d-flex.flex-column')?.querySelector('span.text-success.ms-1');

        if (data.platform_discount_amount > 0) {
            commissionBase.innerHTML = `<span class="text-decoration-line-through text-danger">${formatNumber(data.base_commission)} تومان</span>`;
            commissionBase.classList.remove('d-none');
            if (commissionDiscountLabel) {
                commissionDiscountLabel.textContent = `تخفیف: ${formatNumber(data.platform_discount_amount)} تومان`;
                commissionDiscountLabel.classList.remove('d-none');
            }
        } else {
            commissionBase.innerHTML = '';
            commissionBase.classList.add('d-none');
            if (commissionDiscountLabel) {
                commissionDiscountLabel.classList.add('d-none');
            }
        }
    }

    // ---------------------------------------------------------
    // 4. مبالغ کل و قابل پرداخت
    // ---------------------------------------------------------
    const finalTotalDisplay = document.getElementById('final-total-display');
    if (finalTotalDisplay && data.final_total !== undefined) {
        finalTotalDisplay.textContent = `${formatNumber(data.final_total)} تومان`;
    }

    const payableRow = document.getElementById('payable-row');
    const payableAmountDisplay = document.getElementById('payable-amount-display');
    if (payableRow && payableAmountDisplay) {
        if (data.discount_amount > 0) {
            payableRow.classList.remove('d-none');
            payableAmountDisplay.textContent = `${formatNumber(data.payable_amount)} تومان`;
        } else {
            payableRow.classList.add('d-none');
        }
    }

    // ---------------------------------------------------------
    // 5. نوار نهایی (قیمت نهایی و مجموع تخفیف)
    // ---------------------------------------------------------
    const finalPriceValue = document.getElementById('final-price-value');
    if (finalPriceValue && data.payable_amount !== undefined) {
        finalPriceValue.innerHTML = `${formatNumber(data.payable_amount)} <span class="final-price-unit">تومان</span>`;
    }

    // به‌روزرسانی همه المان‌های دارای شناسه 'total-discount-value'
    const discountValueElements = document.querySelectorAll('#total-discount-value');
    if (discountValueElements.length && data.discount_amount !== undefined) {
        discountValueElements.forEach(el => {
            el.textContent = formatNumber(data.discount_amount);
        });
    }

    // نمایش/مخفی کردن بخش اطلاعات تخفیف در پایین
    const totalDiscountInfo = document.getElementById('total-discount-info');
    if (totalDiscountInfo) {
        if (data.discount_amount > 0) {
            totalDiscountInfo.classList.remove('d-none');
        } else {
            totalDiscountInfo.classList.add('d-none');
        }
    }

    // ---------------------------------------------------------
    // 6. ردیف "مجموع تخفیف‌ها" در کارت هزینه‌ها
    // ---------------------------------------------------------
    const totalDiscountRow = document.getElementById('total-discount-row');
    if (totalDiscountRow) {
        if (data.discount_amount > 0) {
            totalDiscountRow.classList.remove('d-none');
        } else {
            totalDiscountRow.classList.add('d-none');
        }
    }
}