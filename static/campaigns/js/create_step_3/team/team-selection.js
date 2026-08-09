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

    // ========== دریافت CSRF Token ==========
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach(function(cookie) {
                const c = cookie.trim();
                if (c.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(c.slice(name.length + 1));
                }
            });
        }
        return cookieValue;
    }

    // ========== دریافت اطلاعات از DOM ==========
    function getInfluencerCost() {
        const el = document.getElementById('influencer-total-cost');
        if (!el) return 0;
        const raw = el.dataset.cost || '0';
        const cleaned = raw.replace(/,/g, '');
        const val = parseInt(cleaned, 10) || 0;
        return val;
    }

    function getOldContentCost() {
        const el = document.getElementById('old-content-cost');
        if (!el) return 0;
        const raw = el.dataset.cost || '0';
        const cleaned = raw.replace(/,/g, '');
        const val = parseInt(cleaned, 10) || 0;
        return val;
    }

    function getIsReplacementMode() {
        return window.IS_REPLACEMENT_MODE === true;
    }

    function getCampaignId() {
        return window.CAMPAIGN_ID || null;
    }

    // ========== دریافت قیمت دقیق از سرور ==========
    function fetchAccuratePrice(planId, planPrice, teamName, planName) {
        if (!planId) return;

        const isReplacementMode = getIsReplacementMode();
        if (!isReplacementMode) return;

        const campaignId = getCampaignId();
        if (!campaignId) {
            updatePriceUIWithTax(planPrice, 0, 0, planPrice, teamName, planName, null);
            return;
        }

        const url = '/campaigns/api/calculate-team-replacement/';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
                plan_id: planId,
                campaign_id: campaignId
            }),
        })
        .then(function(res) {
            return res.json();
        })
        .then(function(data) {
            if (data.success) {
                updatePriceUIWithTax(
                    planPrice,
                    data.commission_diff || 0,
                    data.vat_diff || 0,
                    data.total_deduct || planPrice,
                    teamName,
                    planName,
                    data
                );
            } else {
                console.error('❌ خطا از سرور:', data.error);
                updatePriceUIWithTax(planPrice, 0, 0, planPrice, teamName, planName, null);
            }
        })
        .catch(function(error) {
            console.error('❌ خطا در fetch:', error);
            updatePriceUIWithTax(planPrice, 0, 0, planPrice, teamName, planName, null);
        });
    }

    // ========== به‌روزرسانی نوار قیمت با مالیات ==========
    function updatePriceUIWithTax(price, commissionDiff, vatDiff, totalDeduct, teamName, planName, data) {
        const isReplacementMode = getIsReplacementMode();

        if (!isReplacementMode) {
            updatePriceUI({ price, teamName, name: planName });
            return;
        }

        // به‌روزرسانی قیمت کلی
        if (totalPriceEl) {
            totalPriceEl.textContent = formatPrice(price);
        }

        // ========== استفاده از breakdown ارسالی از سرور ==========
        let html = '';
        if (data && data.breakdown && data.breakdown.length) {
            data.breakdown.forEach(function(item) {
                let color = '';
                let icon = '';
                if (item.is_total) {
                    color = 'color:#22c55e; font-weight:bold; font-size:1.2rem;';
                    icon = '💰 ';
                } else if (item.is_warning) {
                    color = 'color:#f97316;';
                } else if (item.is_success) {
                    color = 'color:#22c55e;';
                }
                html += `<span class="d-block" style="${color}">${icon}${escapeHtml(item.label)}: ${escapeHtml(item.formatted)} تومان</span>`;
            });
        } else {
            // fallback
            html += `<span class="d-block text-light">📊 ${escapeHtml(teamName)} - ${escapeHtml(planName)}</span>`;
            html += `<span class="d-block text-light">هزینه تیم جدید: ${formatPrice(price)}</span>`;

            if (commissionDiff > 0) {
                html += `<span class="d-block" style="color:#f97316;">➕ مابه‌التفاوت حق‌العمل: ${formatPrice(commissionDiff)}</span>`;
            }
            if (vatDiff > 0) {
                html += `<span class="d-block" style="color:#e74c3c;">➕ مابه‌التفاوت مالیات: ${formatPrice(vatDiff)}</span>`;
            } else if (vatDiff < 0) {
                html += `<span class="d-block text-success">➖ کاهش مالیات (کمک هزینه): ${formatPrice(Math.abs(vatDiff))}</span>`;
            }
            html += `<span class="d-block mt-2" style="color:#22c55e; font-weight:bold; font-size:1.2rem;">💰 مبلغ قابل پرداخت: ${formatPrice(totalDeduct)}</span>`;
        }

        if (breakdownEl) {
            breakdownEl.innerHTML = html;
        }

        // به‌روزرسانی نمایش مبلغ نهایی
        if (finalTotalDisplay) {
            finalTotalDisplay.textContent = formatPrice(totalDeduct);
            finalTotalDisplay.style.color = '#22c55e';
            finalTotalDisplay.style.fontWeight = 'bold';
            finalTotalDisplay.style.display = 'block';
        }

        // نمایش مابه‌التفاوت کمیسیون
        if (commissionDiffDisplay) {
            if (commissionDiff > 0) {
                commissionDiffDisplay.style.display = 'block';
                commissionDiffAmount.textContent = formatPrice(commissionDiff);
                commissionDiffAmount.style.color = '#f97316';
            } else {
                commissionDiffDisplay.style.display = 'none';
            }
        }

        // فعال کردن دکمه submit
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '✅ انتخاب تیم جایگزین';
            submitBtn.classList.remove('opacity-50');
        }

        if (summaryBar) {
            summaryBar.classList.add('has-selection');
        }
    }

    // ========== به‌روزرسانی نوار قیمت (حالت عادی) ==========
    function updatePriceUI(plan, commissionDiff = 0, totalDeduct = 0) {
        const isReplacementMode = getIsReplacementMode();

        if (!plan) {
            if (summaryBar) summaryBar.classList.remove('has-selection');
            if (totalPriceEl) totalPriceEl.textContent = '۰ تومان';
            if (breakdownEl) breakdownEl.innerHTML = '';
            if (selectedCountEl) selectedCountEl.textContent = toPersianNum(0);
            if (submitBtn) submitBtn.disabled = true;

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

        if (breakdownEl) {
            breakdownEl.innerHTML = `
                <span class="d-block text-light">${escapeHtml(plan.teamName)} - ${escapeHtml(plan.name)}</span>
                <span class="d-block mt-1" style="color:#a5b4fc;">${formatPrice(plan.price)}</span>
            `;
        }

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
            if (breakdownEl) {
                breakdownEl.innerHTML = `
                    <span class="d-block text-light">${escapeHtml(plan.teamName)} - ${escapeHtml(plan.name)}</span>
                    <span class="d-block mt-1" style="color:#a5b4fc;">هزینه تیم: ${formatPrice(plan.price)}</span>
                    <span class="d-block" style="color:#f97316;">مابه‌التفاوت حق العمل: +${formatPrice(commissionDiff)}</span>
                    <span class="d-block mt-1" style="color:#22c55e; font-weight:bold;">مبلغ قابل پرداخت: ${formatPrice(totalDeduct)}</span>
                `;
            }
        } else {
            if (commissionDiffDisplay) {
                commissionDiffDisplay.style.display = 'none';
            }
            if (finalTotalDisplay && !isReplacementMode) {
                finalTotalDisplay.textContent = '';
                finalTotalDisplay.style.display = 'none';
            } else if (finalTotalDisplay && isReplacementMode) {
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

        if (isReplacementMode) {
            const campaignId = getCampaignId();
            if (campaignId) {
                updatePriceUI(planObj, 0, planObj.price);
                fetchAccuratePrice(planId, planObj.price, planObj.teamName, planObj.name);
            } else {
                updatePriceUI(planObj, 0, planObj.price);
            }
        } else {
            updatePriceUI(planObj);
        }

        document.querySelectorAll('.plan-card').forEach(card => card.classList.remove('selected-plan-card'));
        const selectedCard = document.querySelector(`.plan-card[data-plan-id="${planId}"]`);
        if (selectedCard) selectedCard.classList.add('selected-plan-card');

        document.dispatchEvent(new CustomEvent('planSelected', {
            detail: {
                planId,
                plan: planObj
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

            const isTimeUnit = (plan.pricing_unit === 'second' || plan.pricing_unit === 'minute');
            const isQuantityUnit = (plan.pricing_unit === 'quantity');

            const hasRange = isTimeUnit && plan.min_quantity && plan.max_quantity &&
                plan.min_quantity !== plan.max_quantity;

            let quantityDisplay = '';
            if (isQuantityUnit && plan.delivery_options_count) {
                quantityDisplay = `${plan.delivery_options_count} گزینه`;
            }

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
                        ${(rangeDisplay || quantityDisplay) ? `
                            <div class="plan-range mt-1">
                                <span class="badge bg-faded-light">
                                    ${escapeHtml(rangeDisplay || quantityDisplay)}
                                </span>
                            </div>
                        ` : ''}
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
                        <a href="/content_team/team/plan/${plan.id}/?from=create_campaign&page=${currentPage}" onclick="event.stopPropagation();" class="btn-view-profile">مشاهده بیشتر <i class="fi-arrow-left"></i></a>
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

        if (!getIsReplacementMode()) {
            if (commissionDiffDisplay) commissionDiffDisplay.style.display = 'none';
        }
    }

    window.initTeamSelection = initTeamSelection;
})();