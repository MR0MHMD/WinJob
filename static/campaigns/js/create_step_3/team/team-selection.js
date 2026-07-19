(function () {
    'use strict';

    // عناصر DOM
    const plansSection = document.getElementById('plans-section');
    const plansContainer = document.getElementById('plans-container');
    const selectedTeamNameSpan = document.getElementById('selected-team-name');
    const hiddenPlanInput = document.querySelector('input[name="selected_plan"]');
    const submitBtn = document.getElementById('submit-btn');
    const summaryBar = document.getElementById('price-summary-bar');
    const totalPriceEl = document.getElementById('total-price-display');
    const breakdownEl = document.getElementById('price-breakdown');
    const selectedCountEl = document.getElementById('selected-count');
    const commissionDiffDisplay = document.getElementById('commission-diff-display');
    const commissionDiffAmount = document.getElementById('commission-diff-amount');
    const finalTotalDisplay = document.getElementById('final-total-display');

    let currentSelectedPlan = null;
    const COMMISSION_RATE = 0.15;

    // ========== توابع کمکی ==========
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/[&<>]/g, function (m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    function toPersianNum(num) {
        return String(num).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
    }

    function formatPrice(price) {
        return toPersianNum(Number(price).toLocaleString('en-US')) + ' تومان';
    }

    function calculateCommission(subtotal) {
        return Math.floor(subtotal * COMMISSION_RATE);
    }

    // ========== دریافت اطلاعات از DOM ==========
    function getInfluencerCost() {
        const el = document.getElementById('influencer-total-cost');
        if (!el) return 0;
        const raw = el.dataset.cost || '0';
        // حذف کاما برای اطمینان (اگر از سمت سرور درست نیومده باشه)
        const cleaned = raw.replace(/,/g, '');
        const val = parseInt(cleaned, 10) || 0;
        console.log('influencerCost:', val);
        return val;
    }

    function getOldContentCost() {
        const el = document.getElementById('old-content-cost');
        if (!el) return 0;
        const raw = el.dataset.cost || '0';
        const cleaned = raw.replace(/,/g, '');
        const val = parseInt(cleaned, 10) || 0;
        console.log('oldContentCost:', val);
        return val;
    }

    function getIsReplacementMode() {
        return window.IS_REPLACEMENT_MODE === true;
    }

    // ========== به‌روزرسانی نوار قیمت ==========
    // ========== به‌روزرسانی نوار قیمت ==========
    function updatePriceUI(plan, commissionDiff = 0, totalDeduct = 0) {
        const isReplacementMode = getIsReplacementMode();

        if (!plan) {
            if (summaryBar) summaryBar.classList.remove('has-selection');
            if (totalPriceEl) totalPriceEl.textContent = '۰ تومان';
            if (breakdownEl) breakdownEl.innerHTML = '';
            if (selectedCountEl) selectedCountEl.textContent = toPersianNum(0);
            if (submitBtn) submitBtn.disabled = true;

            // ========== مخفی کردن نمایش مابه‌التفاوت حق العمل (در هر دو حالت) ==========
            if (commissionDiffDisplay) {
                commissionDiffDisplay.style.display = 'none';
            }
            if (finalTotalDisplay) {
                finalTotalDisplay.textContent = '۰ تومان';
            }
            return;
        }

        if (summaryBar) summaryBar.classList.add('has-selection');
        if (selectedCountEl) selectedCountEl.textContent = toPersianNum(1);
        if (totalPriceEl) totalPriceEl.textContent = formatPrice(plan.price);

        // ========== نمایش عادی (هزینه تیم) ==========
        if (breakdownEl) {
            breakdownEl.innerHTML = `
            <span class="d-block text-light">${escapeHtml(plan.teamName)} - ${escapeHtml(plan.name)}</span>
            <span class="d-block mt-1" style="color:#a5b4fc;">${formatPrice(plan.price)}</span>
        `;
        }

        // ========== نمایش مابه‌التفاوت حق العمل (فقط در حالت جایگزینی و اگر مثبت باشد) ==========
        if (isReplacementMode && commissionDiff > 0) {
            if (commissionDiffDisplay) {
                commissionDiffDisplay.style.display = 'block';
                commissionDiffDisplay.style.opacity = '1';
            }
            if (commissionDiffAmount) {
                commissionDiffAmount.textContent = formatPrice(commissionDiff);
                commissionDiffAmount.style.color = '#f97316';
            }
            if (finalTotalDisplay) {
                finalTotalDisplay.textContent = formatPrice(totalDeduct);
                finalTotalDisplay.style.color = '#22c55e';
                finalTotalDisplay.style.fontWeight = 'bold';
            }
            // به‌روزرسانی breakdown با مبلغ کل
            if (breakdownEl) {
                breakdownEl.innerHTML = `
                <span class="d-block text-light">${escapeHtml(plan.teamName)} - ${escapeHtml(plan.name)}</span>
                <span class="d-block mt-1" style="color:#a5b4fc;">هزینه تیم: ${formatPrice(plan.price)}</span>
                <span class="d-block" style="color:#f97316;">مابه‌التفاوت حق العمل: +${formatPrice(commissionDiff)}</span>
                <span class="d-block mt-1" style="color:#22c55e; font-weight:bold;">مبلغ قابل پرداخت: ${formatPrice(totalDeduct)}</span>
            `;
            }
        } else {
            // ========== در حالت عادی یا وقتی کمیسیون صفر هست، مخفی کن ==========
            if (commissionDiffDisplay) {
                commissionDiffDisplay.style.display = 'none';
            }
            // در حالت عادی، فقط هزینه تیم رو نشون بده
            if (finalTotalDisplay && !isReplacementMode) {
                finalTotalDisplay.textContent = '';  // یا مخفی کن
                finalTotalDisplay.style.display = 'none';
            } else if (finalTotalDisplay && isReplacementMode) {
                // در حالت جایگزینی با کمیسیون صفر، مبلغ قابل پرداخت = هزینه تیم
                finalTotalDisplay.textContent = formatPrice(plan.price);
                finalTotalDisplay.style.color = '#22c55e';
                finalTotalDisplay.style.fontWeight = 'bold';
                finalTotalDisplay.style.display = 'block';
            }
        }

        if (submitBtn) submitBtn.disabled = false;
    }

    // ========== انتخاب پلن ==========
    function selectPlan(planId, planObj) {
        if (hiddenPlanInput) hiddenPlanInput.value = planId;
        currentSelectedPlan = planObj;

        const isReplacementMode = getIsReplacementMode();
        let commissionDiff = 0;
        let totalDeduct = planObj.price;

        // ========== محاسبه مابه‌التفاوت حق العمل (فقط در حالت جایگزینی) ==========
        if (isReplacementMode) {
            const influencerCost = getInfluencerCost();
            const oldContentCost = getOldContentCost();
            const newContentCost = planObj.price;

            // محاسبه کل مبلغ قبلی و جدید
            const oldSubtotal = influencerCost + oldContentCost;
            const newSubtotal = influencerCost + newContentCost;

            // محاسبه کمیسیون قبلی و جدید
            const oldCommission = calculateCommission(oldSubtotal);
            const newCommission = calculateCommission(newSubtotal);

            // مابه‌التفاوت (فقط مثبت)
            commissionDiff = Math.max(newCommission - oldCommission, 0);
            totalDeduct = newContentCost + commissionDiff;
        }

        updatePriceUI(planObj, commissionDiff, totalDeduct);

        // علامت‌گذاری کارت انتخاب شده
        document.querySelectorAll('.plan-card').forEach(card => card.classList.remove('selected-plan-card'));
        const selectedCard = document.querySelector(`.plan-card[data-plan-id="${planId}"]`);
        if (selectedCard) selectedCard.classList.add('selected-plan-card');

        document.dispatchEvent(new CustomEvent('planSelected', {
            detail: {
                planId,
                commissionDiff,
                totalDeduct
            }
        }));
    }

    // ========== رندر کارت‌های پلن ==========
    function renderPlansForTeam(teamId, teamName, plans) {
        if (!plans || plans.length === 0) {
            if (plansSection) plansSection.style.display = 'none';
            return;
        }
        if (selectedTeamNameSpan) selectedTeamNameSpan.textContent = teamName;
        if (plansContainer) plansContainer.innerHTML = '';

        plans.forEach((plan, idx) => {
            const isPopular = plan.is_most_popular || false;

            // ========== تشخیص نوع واحد ==========
            const isTimeUnit = (plan.pricing_unit === 'second' || plan.pricing_unit === 'minute');
            const isQuantityUnit = (plan.pricing_unit === 'quantity');

            // محدوده برای SECOND/MINUTE
            const hasRange = isTimeUnit && plan.min_quantity && plan.max_quantity &&
                plan.min_quantity !== plan.max_quantity;

            // ========== ✅ نمایش تعداد برای QUANTITY (از delivery_options_count) ==========
            let quantityDisplay = '';
            if (isQuantityUnit && plan.delivery_options_count) {
                quantityDisplay = `${plan.delivery_options_count} گزینه`;
            }

            // محدوده نمایشی برای SECOND/MINUTE
            let rangeDisplay = '';
            if (hasRange) {
                rangeDisplay = plan.quantity_display || '';
            } else if (isTimeUnit && plan.base_quantity) {
                const unitLabels = {
                    'second': 'ثانیه',
                    'minute': 'دقیقه',
                    'quantity': 'عدد'
                };
                const unit = unitLabels[plan.pricing_unit] || '';
                rangeDisplay = `${plan.base_quantity} ${unit}`;
            }

            const col = document.createElement('div');
            const currentPage = new URLSearchParams(window.location.search).get('page') || '1';
            col.className = 'col-md-6 col-lg-4 mb-4';
            col.innerHTML = `
            <div class="plan-card ${isPopular ? 'plan-card-popular' : ''}" data-plan-id="${plan.id}">
                <div class="plan-selection-indicator">
                    <i class="fi-check-circle selected-icon"></i>
                    <i class="fi-circle unselected-icon"></i>
                </div>
                ${isPopular ? '<div class="popular-badge">⭐ محبوب‌ترین</div>' : ''}
                <div class="plan-preview">
                    <div class="plan-preview-icon">
                        <i class="${plan.service_type_icon || 'fi-star'}"></i>
                    </div>
                </div>
                <div class="plan-header">
                    <h4 class="plan-name">${escapeHtml(plan.name)}</h4>
                    <div class="plan-price">
                        <span class="price-number">${formatPrice(plan.price)}</span>
                    </div>
                    
                    <!-- ========== ✅ نمایش محدوده یا تعداد گزینه‌ها ========== -->
                    ${(rangeDisplay || quantityDisplay) ? `
                        <div class="plan-range mt-1">
                            <span class="badge bg-faded-light">
                                ${escapeHtml(rangeDisplay || quantityDisplay)}
                            </span>
                        </div>
                    ` : ''}
                    
                    <!-- ========== ✅ میانگین امتیاز ========== -->
                    <div class="plan-rating mt-1">
                        ${plan.avg_rating ? `
                            <span class="badge bg-warning bg-opacity-10 text-warning">
                                <i class="fi-star-filled me-1"></i> ${plan.avg_rating}
                            </span>
                        ` : `
                            <span class="badge bg-secondary bg-opacity-10 text-muted">
                                <i class="fi-star me-1"></i> بدون امتیاز
                            </span>
                        `}
                    </div>
                </div>
                <div class="plan-body">
                    <p class="plan-description">${escapeHtml(plan.description) || 'توضیحاتی ثبت نشده است.'}</p>
                    ${plan.features && plan.features.length ? `
                        <div class="plan-features">
                            <div class="fw-semibold text-light mb-1">✨ ویژگی‌ها:</div>
                            <ul>
                                ${plan.features.slice(0, 3).map(f => `<li><i class="fi-check-circle text-success me-1"></i> ${escapeHtml(f)}</li>`).join('')}
                                ${plan.features.length > 3 ? `<li class="text-secondary">...</li>` : ''}
                            </ul>
                        </div>
                    ` : ''}
                    <div class="plan-delivery">
                        <i class="fi-clock text-primary"></i> <span>تحویل: ${plan.delivery_days} روز کاری</span>
                        <span class="mx-1 text-muted">•</span>
                        <span class="text-muted">${escapeHtml(plan.delivery_type_display || '')}</span>
                    </div>
                </div>
                <div class="plan-footer text-center">
                    <a href="/content_team/plan/${plan.id}/?from=create_campaign&page=${currentPage}" onclick="event.stopPropagation();" class="btn-view-profile">مشاهده بیشتر <i class="fi-arrow-left"></i></a>
                </div>
            </div>
        `;
            if (plansContainer) plansContainer.appendChild(col);
        });

        if (plansSection) {
            plansSection.style.display = 'block';
            plansSection.scrollIntoView({behavior: 'smooth', block: 'start'});
        }

        document.querySelectorAll('.plan-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.btn-view-profile')) return;
                if (e.target.closest('.btn-more')) return;
                const planId = parseInt(card.dataset.planId);
                const plan = plans.find(p => p.id === planId);
                if (plan) selectPlan(planId, {...plan, teamName});
            });
        });
    }

    // ========== تابع اصلی ==========
    function initTeamSelection() {
        // کلیک روی کارت تیم
        document.querySelectorAll('.team-card-wrapper').forEach(wrapper => {
            const teamInner = wrapper.querySelector('.team-card-inner');
            if (!teamInner) return;

            const teamId = wrapper.dataset.teamId;
            const teamName = wrapper.dataset.teamName;
            let plans = [];
            try {
                plans = JSON.parse(wrapper.dataset.plans || '[]');
            } catch (e) {
                console.error("Invalid plans JSON", e);
            }

            teamInner.addEventListener('click', (e) => {
                if (e.target.closest('.btn')) return;
                if (e.target.closest('.btn-view-profile')) return;

                document.querySelectorAll('.team-card-inner').forEach(card => card.classList.remove('selected'));
                teamInner.classList.add('selected');

                renderPlansForTeam(teamId, teamName, plans);

                if (hiddenPlanInput) hiddenPlanInput.value = '';
                currentSelectedPlan = null;
                updatePriceUI(null);
                document.dispatchEvent(new CustomEvent('planCleared'));
            });
        });

        // ========== انتخاب خودکار ==========
        const preselectedTeamId = window.PRESELECT_TEAM_ID;
        const preselectedPlanId = window.PRESELECT_PLAN_ID;

        if (preselectedTeamId && preselectedPlanId) {
            const targetWrapper = Array.from(document.querySelectorAll('.team-card-wrapper')).find(
                wrapper => parseInt(wrapper.dataset.teamId) === preselectedTeamId
            );
            if (targetWrapper) {
                const teamInner = targetWrapper.querySelector('.team-card-inner');
                if (teamInner) {
                    teamInner.classList.add('selected');
                    const teamId = targetWrapper.dataset.teamId;
                    const teamName = targetWrapper.dataset.teamName;
                    let plans = [];
                    try {
                        plans = JSON.parse(targetWrapper.dataset.plans || '[]');
                    } catch (e) {
                    }
                    renderPlansForTeam(teamId, teamName, plans);
                    const planToSelect = plans.find(p => p.id === preselectedPlanId);
                    if (planToSelect) {
                        selectPlan(preselectedPlanId, {...planToSelect, teamName});
                    }
                }
            }
        } else if (preselectedPlanId && !preselectedTeamId) {
            for (let wrapper of document.querySelectorAll('.team-card-wrapper')) {
                let plans = [];
                try {
                    plans = JSON.parse(wrapper.dataset.plans || '[]');
                } catch (e) {
                }
                const found = plans.find(p => p.id === preselectedPlanId);
                if (found) {
                    const teamInner = wrapper.querySelector('.team-card-inner');
                    if (teamInner) {
                        teamInner.classList.add('selected');
                        renderPlansForTeam(wrapper.dataset.teamId, wrapper.dataset.teamName, plans);
                        selectPlan(preselectedPlanId, {...found, teamName: wrapper.dataset.teamName});
                    }
                    break;
                }
            }
        }

        if (preselectedTeamId && !preselectedPlanId) {
            const targetWrapper = Array.from(document.querySelectorAll('.team-card-wrapper')).find(
                wrapper => parseInt(wrapper.dataset.teamId) === preselectedTeamId
            );
            if (targetWrapper) {
                const teamInner = targetWrapper.querySelector('.team-card-inner');
                if (teamInner) teamInner.classList.add('selected');
                const teamId = targetWrapper.dataset.teamId;
                const teamName = targetWrapper.dataset.teamName;
                let plans = [];
                try {
                    plans = JSON.parse(targetWrapper.dataset.plans || '[]');
                } catch (e) {
                }
                renderPlansForTeam(teamId, teamName, plans);
                if (hiddenPlanInput) hiddenPlanInput.value = '';
                currentSelectedPlan = null;
                updatePriceUI(null);
                document.dispatchEvent(new CustomEvent('planCleared'));
            }
        }

        const existingPlanId = hiddenPlanInput ? parseInt(hiddenPlanInput.value) : null;
        if (existingPlanId && !isNaN(existingPlanId) && !preselectedPlanId) {
            for (let wrapper of document.querySelectorAll('.team-card-wrapper')) {
                let plans = [];
                try {
                    plans = JSON.parse(wrapper.dataset.plans || '[]');
                } catch (e) {
                }
                const found = plans.find(p => p.id === existingPlanId);
                if (found) {
                    const teamInner = wrapper.querySelector('.team-card-inner');
                    if (teamInner) teamInner.classList.add('selected');
                    renderPlansForTeam(wrapper.dataset.teamId, wrapper.dataset.teamName, plans);
                    selectPlan(existingPlanId, {...found, teamName: wrapper.dataset.teamName});
                    break;
                }
            }
        }

        // ========== اگه حالت جایگزینی نباشه، نمایش مابه‌التفاوت رو مخفی کن ==========
        if (!getIsReplacementMode()) {
            if (commissionDiffDisplay) commissionDiffDisplay.style.display = 'none';
        }
    }

    // ========== مقداردهی اولیه ==========
    window.initTeamSelection = initTeamSelection;
})();