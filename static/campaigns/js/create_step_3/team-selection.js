(function() {
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

    let currentSelectedPlan = null;

    // توابع کمکی
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/[&<>]/g, function(m) {
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

    // به‌روزرسانی نوار قیمت
    function updatePriceUI(plan) {
        if (!plan) {
            if (summaryBar) summaryBar.classList.remove('has-selection');
            if (totalPriceEl) totalPriceEl.textContent = '۰ تومان';
            if (breakdownEl) breakdownEl.innerHTML = '';
            if (selectedCountEl) selectedCountEl.textContent = toPersianNum(0);
            if (submitBtn) submitBtn.disabled = true;
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
        if (submitBtn) submitBtn.disabled = false;
    }

    // رندر کارت‌های پلن برای تیم انتخاب شده
    function renderPlansForTeam(teamId, teamName, plans) {
        if (!plans || plans.length === 0) {
            if (plansSection) plansSection.style.display = 'none';
            return;
        }
        if (selectedTeamNameSpan) selectedTeamNameSpan.textContent = teamName;
        if (plansContainer) plansContainer.innerHTML = '';

        plans.forEach((plan, idx) => {
            const isPopular = (plans.length === 3 && idx === 1);
            const col = document.createElement('div');
            col.className = 'col-md-6 col-lg-4 mb-4';
            col.innerHTML = `
                <div class="plan-card ${isPopular ? 'plan-card-popular' : ''}" data-plan-id="${plan.id}">
                    <div class="plan-selection-indicator">
                        <i class="fi-check-circle selected-icon"></i>
                        <i class="fi-circle unselected-icon"></i>
                    </div>
                    ${isPopular ? '<div class="popular-badge">⭐ پرطرفدار</div>' : ''}
                    <div class="plan-preview">
                        <div class="plan-preview-icon">
                            <i class="${plan.service_type_icon || 'fi-star'}"></i>
                        </div>
                    </div>
                    <div class="plan-header">
                        <h4 class="plan-name">${escapeHtml(plan.name)}</h4>
                        <div class="plan-price">
                            <span class="price-number">${formatPrice(plan.price)}</span>
                            ${plan.price_per_unit && window.CONTENT_MINUTES ?
                                `<span class="price-unit">(${formatPrice(plan.price_per_unit)} هر دقیقه)</span>` : ''}
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
                        </div>
                    </div>
                    <div class="plan-footer">
                        <a href="/content_team/plan/${plan.id}/?from=create_campaign" class="btn btn-sm btn-more w-100">مشاهده بیشتر <i class="fi-arrow-left"></i></a>
                    </div>
                </div>
            `;
            if (plansContainer) plansContainer.appendChild(col);
        });

        if (plansSection) {
            plansSection.style.display = 'block';
            plansSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        // افزودن رویداد کلیک به کارت‌های پلن
        document.querySelectorAll('.plan-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.btn-more')) return;
                const planId = parseInt(card.dataset.planId);
                const plan = plans.find(p => p.id === planId);
                if (plan) selectPlan(planId, { ...plan, teamName });
            });
        });
    }

    function selectPlan(planId, planObj) {
        if (hiddenPlanInput) hiddenPlanInput.value = planId;
        currentSelectedPlan = planObj;
        updatePriceUI(planObj);

        document.querySelectorAll('.plan-card').forEach(card => card.classList.remove('selected-plan-card'));
        const selectedCard = document.querySelector(`.plan-card[data-plan-id="${planId}"]`);
        if (selectedCard) selectedCard.classList.add('selected-plan-card');

        document.dispatchEvent(new CustomEvent('planSelected', { detail: { planId } }));
    }

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
            } catch(e) { console.error("Invalid plans JSON", e); }

            teamInner.addEventListener('click', (e) => {
                if (e.target.closest('.btn')) return;

                document.querySelectorAll('.team-card-inner').forEach(card => card.classList.remove('selected'));
                teamInner.classList.add('selected');

                renderPlansForTeam(teamId, teamName, plans);

                if (hiddenPlanInput) hiddenPlanInput.value = '';
                currentSelectedPlan = null;
                updatePriceUI(null);
                document.dispatchEvent(new CustomEvent('planCleared'));
            });
        });

        // انتخاب خودکار از طریق پارامترهای URL (بازگشت از صفحه جزئیات)
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
                    try { plans = JSON.parse(targetWrapper.dataset.plans || '[]'); } catch(e) {}
                    renderPlansForTeam(teamId, teamName, plans);
                    const planToSelect = plans.find(p => p.id === preselectedPlanId);
                    if (planToSelect) {
                        selectPlan(preselectedPlanId, { ...planToSelect, teamName });
                    }
                }
            }
        } else if (preselectedPlanId && !preselectedTeamId) {
            for (let wrapper of document.querySelectorAll('.team-card-wrapper')) {
                let plans = [];
                try { plans = JSON.parse(wrapper.dataset.plans || '[]'); } catch(e) {}
                const found = plans.find(p => p.id === preselectedPlanId);
                if (found) {
                    const teamInner = wrapper.querySelector('.team-card-inner');
                    if (teamInner) {
                        teamInner.classList.add('selected');
                        renderPlansForTeam(wrapper.dataset.teamId, wrapper.dataset.teamName, plans);
                        selectPlan(preselectedPlanId, { ...found, teamName: wrapper.dataset.teamName });
                    }
                    break;
                }
            }
        }

        // انتخاب خودکار در حالت ویرایش کمپین
        const existingPlanId = hiddenPlanInput ? parseInt(hiddenPlanInput.value) : null;
        if (existingPlanId && !isNaN(existingPlanId) && !preselectedPlanId) {
            for (let wrapper of document.querySelectorAll('.team-card-wrapper')) {
                let plans = [];
                try { plans = JSON.parse(wrapper.dataset.plans || '[]'); } catch(e) {}
                const found = plans.find(p => p.id === existingPlanId);
                if (found) {
                    const teamInner = wrapper.querySelector('.team-card-inner');
                    if (teamInner) teamInner.classList.add('selected');
                    renderPlansForTeam(wrapper.dataset.teamId, wrapper.dataset.teamName, plans);
                    selectPlan(existingPlanId, { ...found, teamName: wrapper.dataset.teamName });
                    break;
                }
            }
        }
    }

    window.initTeamSelection = initTeamSelection;
})();