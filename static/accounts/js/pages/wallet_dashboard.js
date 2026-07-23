/**
 * داشبورد کیف پول - اسکریپت‌های اختصاصی
 */

(function() {
    'use strict';

    let currentPage = 2;
    let isLoading = false;
    let hasMore = true;
    const loadMoreBtn = document.getElementById('loadMoreTransactions');
    const transactionsList = document.getElementById('transactionsList');

    async function loadMoreTransactions() {
        if (isLoading || !hasMore) return;

        isLoading = true;

        if (loadMoreBtn) {
            loadMoreBtn.innerHTML = '<span class="loading-spinner"></span> در حال بارگذاری...';
            loadMoreBtn.disabled = true;
        }

        try {
            const response = await fetch(`/payment/wallet/transactions/load-more/?page=${currentPage}`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });

            if (!response.ok) throw new Error('خطا در ارتباط با سرور');

            const data = await response.json();

            if (data.error) throw new Error(data.message || 'خطا در بارگذاری');

            if (data.transactions && data.transactions.length > 0) {
                data.transactions.forEach((transaction, index) => {
                    const transactionHtml = createTransactionElement(transaction, index);
                    transactionsList.insertAdjacentHTML('beforeend', transactionHtml);
                });

                hasMore = data.has_more;
                if (hasMore) currentPage++;

                if (!hasMore && loadMoreBtn) {
                    loadMoreBtn.innerHTML = '✅ همه تراکنش‌ها نمایش داده شد';
                    loadMoreBtn.disabled = true;
                    setTimeout(() => {
                        if (loadMoreBtn && loadMoreBtn.parentElement) {
                            loadMoreBtn.parentElement.style.display = 'none';
                        }
                    }, 2000);
                }
            } else {
                hasMore = false;
                if (loadMoreBtn) {
                    loadMoreBtn.innerHTML = '✅ همه تراکنش‌ها نمایش داده شد';
                    loadMoreBtn.disabled = true;
                    setTimeout(() => {
                        if (loadMoreBtn && loadMoreBtn.parentElement) {
                            loadMoreBtn.parentElement.style.display = 'none';
                        }
                    }, 2000);
                }
            }
        } catch (error) {
            console.error('خطا:', error);
        } finally {
            isLoading = false;
            if (loadMoreBtn && hasMore) {
                loadMoreBtn.innerHTML = '<i class="fi-arrow-down ms-1"></i> مشاهده بیشتر';
                loadMoreBtn.disabled = false;
            }
        }
    }

    function createTransactionElement(transaction, index) {
        let iconClass = 'fi-info-circle';
        let iconBgClass = 'other';

        switch(transaction.type) {
            case 'deposit':
                iconClass = 'fi-plus-circle';
                iconBgClass = 'deposit';
                break;
            case 'withdraw':
                iconClass = 'fi-minus-circle';
                iconBgClass = 'withdraw';
                break;
            case 'purchase':
                iconClass = 'fi-cart';
                iconBgClass = 'purchase';
                break;
        }

        const amountClass = transaction.is_income ? 'income' : 'expense';
        const sign = transaction.is_income ? '+' : '-';
        const delay = (index * 0.05) % 0.3;

        return `
            <div class="transaction-item" style="animation-delay: ${delay}s">
                <div class="d-flex align-items-center">
                    <div class="transaction-icon ${iconBgClass}">
                        <i class="${iconClass} fs-5"></i>
                    </div>
                    <div class="transaction-info">
                        <div class="transaction-title">${escapeHtml(transaction.title)}</div>
                        <div class="transaction-date">${escapeHtml(transaction.date)}</div>
                        ${transaction.description ? `<div class="transaction-desc">${escapeHtml(transaction.description)}</div>` : ''}
                    </div>
                </div>
                <div class="transaction-amount ${amountClass}">
                    ${sign} ${formatNumberWithCommas(transaction.amount)} تومان
                </div>
            </div>
        `;
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatNumberWithCommas(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', loadMoreTransactions);

        const totalTransactions = document.querySelectorAll('.transaction-item').length;
        if (totalTransactions < 5) {
            if (loadMoreBtn.parentElement) {
                loadMoreBtn.parentElement.style.display = 'none';
            }
        }
    }

    console.log('داشبورد کیف پول آماده است 🚀');
})();