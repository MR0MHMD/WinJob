// ==================== مدیریت مودال ثبت نظر تیم ====================
document.addEventListener('DOMContentLoaded', function() {
    // داده‌های ارسالی از تمپلیت
    const reviewData = window.teamReviewData || {};
    const canSubmitReview = reviewData.canSubmitReview || false;
    const pendingOrdersCount = reviewData.pendingOrdersCount || 0;
    const teamId = reviewData.teamId || null;
    const csrftoken = reviewData.csrfToken || getCookie('csrftoken');
    const submitUrl = reviewData.submitUrl || '';
    const editUrl = reviewData.editUrl || '';

    // توابع کمکی
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const reviewModalEl = document.getElementById('reviewModal');
    let reviewModal = null;
    if (reviewModalEl) {
        reviewModal = new bootstrap.Modal(reviewModalEl);
    }

    const storageKey = `review_modal_closed_team_${teamId}`;
    const urlParams = new URLSearchParams(window.location.search);
    const reviewParam = urlParams.get('review_booking_id');

    // نمایش خودکار مودال
    if (reviewParam && canSubmitReview) {
        setTimeout(() => {
            if (reviewModal) reviewModal.show();
        }, 500);
    } else if (pendingOrdersCount > 0 && !sessionStorage.getItem(storageKey)) {
        setTimeout(() => {
            if (reviewModal) reviewModal.show();
        }, 500);
    }

    // رویداد بسته شدن مودال
    if (reviewModalEl) {
        reviewModalEl.addEventListener('hidden.bs.modal', function () {
            if (!reviewParam) sessionStorage.setItem(storageKey, 'true');
            // ریست فرم
            const form = document.getElementById('reviewForm');
            if (form) form.reset();
            const ratingVal = document.getElementById('ratingValue');
            if (ratingVal) ratingVal.value = '';
            const commentField = document.getElementById('reviewComment');
            if (commentField) commentField.value = '';
            const orderIdField = document.getElementById('reviewOrderId');
            if (orderIdField) orderIdField.value = '';
            const submitBtn = document.getElementById('submitReviewBtn');
            if (submitBtn) submitBtn.innerHTML = '<i class="fi-send ms-1"></i> ثبت نظر';
            window.isEditing = false;
            document.querySelectorAll('#starRatingInput i').forEach(s => s.classList.remove('active'));
            const infoDiv = document.getElementById('reviewOrderInfo');
            if (infoDiv) infoDiv.style.display = 'none';
            const section = document.getElementById('orderSelectionSection');
            if (section) section.style.display = 'block';
        });
    }

    // دکمه دستی ثبت نظر
    const manualBtn = document.getElementById('manualReviewBtn');
    if (manualBtn && reviewModal && canSubmitReview) {
        manualBtn.addEventListener('click', function () {
            const msgDiv = document.getElementById('reviewMessage');
            if (msgDiv) msgDiv.innerHTML = '';
            const section = document.getElementById('orderSelectionSection');
            if (section) section.style.display = 'block';
            const infoDiv = document.getElementById('reviewOrderInfo');
            if (infoDiv) infoDiv.style.display = 'none';
            reviewModal.show();
        });
    }

    // مدیریت ستاره‌ها
    const stars = document.querySelectorAll('#starRatingInput i');
    const ratingInput = document.getElementById('ratingValue');
    if (stars.length && ratingInput) {
        stars.forEach(star => {
            star.addEventListener('click', function () {
                const value = parseInt(this.dataset.value);
                ratingInput.value = value;
                stars.forEach(s => {
                    if (parseInt(s.dataset.value) <= value) {
                        s.classList.add('active');
                    } else {
                        s.classList.remove('active');
                    }
                });
            });
        });
    }

    // ارسال فرم (ثبت نظر جدید یا ویرایش)
    const reviewForm = document.getElementById('reviewForm');
    if (reviewForm) {
        reviewForm.addEventListener('submit', function (e) {
            e.preventDefault();

            // تعیین order_id (برای حالت ثبت جدید)
            if (!window.isEditing) {
                const selectedRadio = document.querySelector('input[name="selected_order"]:checked');
                const orderIdField = document.getElementById('reviewOrderId');
                if (orderIdField) {
                    orderIdField.value = selectedRadio ? selectedRadio.value : '';
                }
            }

            const rating = ratingInput.value;
            if (!rating) {
                const errDiv = document.getElementById('ratingError');
                if (errDiv) errDiv.style.display = 'block';
                return;
            }
            const errDiv = document.getElementById('ratingError');
            if (errDiv) errDiv.style.display = 'none';

            const submitBtn = document.getElementById('submitReviewBtn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> در حال ثبت...';
            }

            const formData = new FormData(reviewForm);
            let url = submitUrl;
            if (window.isEditing) {
                url = editUrl;
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('HTTP error ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const msgDiv = document.getElementById('reviewMessage');
                    if (msgDiv) msgDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                    setTimeout(() => {
                        if (reviewModal) reviewModal.hide();
                        location.reload();
                    }, 2000);
                } else {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = window.isEditing ? '<i class="fi-save ms-1"></i> ویرایش نظر' : '<i class="fi-send ms-1"></i> ثبت نظر';
                    }
                    const msgDiv = document.getElementById('reviewMessage');
                    if (msgDiv) msgDiv.innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = window.isEditing ? '<i class="fi-save ms-1"></i> ویرایش نظر' : '<i class="fi-send ms-1"></i> ثبت نظر';
                }
                const msgDiv = document.getElementById('reviewMessage');
                if (msgDiv) msgDiv.innerHTML = `<div class="alert alert-danger">خطا در ارتباط با سرور: ${error.message}</div>`;
            });
        });
    }

    // دکمه‌های ویرایش نظر (داینامیک)
    function bindEditButtons() {
        document.querySelectorAll('.edit-review-btn').forEach(btn => {
            btn.removeEventListener('click', btn._listener);
            const listener = function (e) {
                e.preventDefault();
                const reviewId = this.dataset.reviewId;
                const oldRating = parseInt(this.dataset.rating);
                const oldComment = this.dataset.comment;
                let orderName = this.dataset.orderName;
                if (!orderName) orderName = 'نظر عمومی';
                const infoDiv = document.getElementById('reviewOrderInfo');
                const nameSpan = document.getElementById('orderNameDisplay');
                if (infoDiv && nameSpan) {
                    nameSpan.innerText = orderName;
                    infoDiv.style.display = 'block';
                }
                const section = document.getElementById('orderSelectionSection');
                if (section) section.style.display = 'none';
                stars.forEach(star => {
                    const val = parseInt(star.dataset.value);
                    if (val <= oldRating) star.classList.add('active');
                    else star.classList.remove('active');
                });
                ratingInput.value = oldRating;
                const commentField = document.getElementById('reviewComment');
                if (commentField) commentField.value = oldComment;
                const orderIdField = document.getElementById('reviewOrderId');
                if (orderIdField) {
                    orderIdField.name = 'review_id';
                    orderIdField.value = reviewId;
                }
                const submitBtn = document.getElementById('submitReviewBtn');
                if (submitBtn) submitBtn.innerHTML = '<i class="fi-save ms-1"></i> ویرایش نظر';
                window.isEditing = true;
                if (reviewModal) reviewModal.show();
            };
            btn.addEventListener('click', listener);
            btn._listener = listener;
        });
    }

    bindEditButtons();
});