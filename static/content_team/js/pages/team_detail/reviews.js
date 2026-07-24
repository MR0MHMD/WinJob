/**
 * ============================================================
 * team_detail_reviews.js
 * مدیریت ثبت، ویرایش و نمایش نظرات تیم
 * ============================================================
 */

(function initReviewSystem() {
    'use strict';

    // ============================================================
    // ۱. دریافت داده‌های اولیه از تمپلیت
    // ============================================================
    const reviewData = window.teamReviewData || {};
    const {
        canSubmitReview = false,
        pendingOrdersCount = 0,
        teamId = null,
        csrfToken = getCookie('csrftoken'),
        submitUrl = '',
        editUrl = ''
    } = reviewData;

    // ============================================================
    // ۲. توابع کمکی
    // ============================================================
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

    function getElement(id) {
        return document.getElementById(id);
    }

    function showMessage(elementId, message, type) {
        const el = getElement(elementId);
        if (!el) return;
        const className = type === 'success' ? 'alert-success' :
            type === 'error' ? 'alert-danger' : 'alert-info';
        el.innerHTML = `<div class="alert ${className}">${message}</div>`;
    }

    function resetForm() {
        const form = getElement('reviewForm');
        if (form) form.reset();

        const ratingVal = getElement('ratingValue');
        if (ratingVal) ratingVal.value = '';

        const commentField = getElement('reviewComment');
        if (commentField) commentField.value = '';

        const orderIdField = getElement('reviewOrderId');
        if (orderIdField) {
            orderIdField.name = 'order_id';
            orderIdField.value = '';
        }

        const stars = document.querySelectorAll('#starRatingInput i');
        stars.forEach(function (s) {
            s.classList.remove('active');
        });

        const infoDiv = getElement('reviewOrderInfo');
        if (infoDiv) infoDiv.style.display = 'none';

        const section = getElement('orderSelectionSection');
        if (section) section.style.display = 'block';

        const submitBtn = getElement('submitReviewBtn');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fi-send ms-1"></i> ثبت نظر';
        }

        window.isEditing = false;
        window.editingReviewId = null;
    }

    // ============================================================
    // ۳. مقداردهی اولیه مودال
    // ============================================================
    const reviewModalEl = getElement('reviewModal');
    let reviewModal = null;
    if (reviewModalEl) {
        reviewModal = new bootstrap.Modal(reviewModalEl, {
            backdrop: 'static',
            keyboard: false
        });
    }

    // ============================================================
    // ۴. نمایش خودکار مودال
    // ============================================================
    const storageKey = `review_modal_closed_team_${teamId}`;
    const urlParams = new URLSearchParams(window.location.search);
    const reviewParam = urlParams.get('review_booking_id');

    if (reviewParam && canSubmitReview) {
        setTimeout(function () {
            if (reviewModal) reviewModal.show();
        }, 500);
    } else if (pendingOrdersCount > 0 && !sessionStorage.getItem(storageKey)) {
        setTimeout(function () {
            if (reviewModal) reviewModal.show();
        }, 500);
    }

    // ============================================================
    // ۵. رویداد بسته شدن مودال
    // ============================================================
    if (reviewModalEl) {
        reviewModalEl.addEventListener('hidden.bs.modal', function () {
            if (!reviewParam) {
                sessionStorage.setItem(storageKey, 'true');
            }
            resetForm();
            const msgDiv = getElement('reviewMessage');
            if (msgDiv) msgDiv.innerHTML = '';
        });
    }

    // ============================================================
    // ۶. دکمه ثبت نظر دستی
    // ============================================================
    const manualBtn = getElement('manualReviewBtn');
    if (manualBtn && reviewModal && canSubmitReview) {
        manualBtn.addEventListener('click', function () {
            resetForm();
            const msgDiv = getElement('reviewMessage');
            if (msgDiv) msgDiv.innerHTML = '';
            reviewModal.show();
        });
    }

    // ============================================================
    // ۷. سیستم امتیازدهی با ستاره
    // ============================================================
    const stars = document.querySelectorAll('#starRatingInput i');
    const ratingInput = getElement('ratingValue');

    if (stars.length && ratingInput) {
        stars.forEach(function (star) {
            star.addEventListener('click', function () {
                const value = parseInt(this.dataset.value, 10);
                ratingInput.value = value;

                stars.forEach(function (s) {
                    const starValue = parseInt(s.dataset.value, 10);
                    if (starValue <= value) {
                        s.classList.add('active');
                    } else {
                        s.classList.remove('active');
                    }
                });

                const errDiv = getElement('ratingError');
                if (errDiv) errDiv.style.display = 'none';
            });

            // هاور effect
            star.addEventListener('mouseenter', function () {
                const value = parseInt(this.dataset.value, 10);
                stars.forEach(function (s) {
                    const starValue = parseInt(s.dataset.value, 10);
                    if (starValue <= value) {
                        s.style.color = '#fbbf24';
                    } else {
                        s.style.color = '';
                    }
                });
            });

            star.addEventListener('mouseleave', function () {
                const selected = parseInt(ratingInput.value, 10) || 0;
                stars.forEach(function (s) {
                    const starValue = parseInt(s.dataset.value, 10);
                    if (starValue <= selected) {
                        s.style.color = '';
                    } else {
                        s.style.color = '';
                    }
                });
            });
        });
    }

    // ============================================================
    // ۸. ارسال فرم (ثبت/ویرایش نظر)
    // ============================================================
    const reviewForm = getElement('reviewForm');
    if (reviewForm) {
        reviewForm.addEventListener('submit', function (e) {
            e.preventDefault();

            // تعیین order_id برای حالت ثبت جدید
            if (!window.isEditing) {
                const selectedRadio = document.querySelector('input[name="selected_order"]:checked');
                const orderIdField = getElement('reviewOrderId');
                if (orderIdField) {
                    orderIdField.value = selectedRadio ? selectedRadio.value : '';
                }
            }

            // اعتبارسنجی امتیاز
            const rating = ratingInput.value;
            if (!rating || parseInt(rating, 10) < 1 || parseInt(rating, 10) > 5) {
                const errDiv = getElement('ratingError');
                if (errDiv) errDiv.style.display = 'block';
                return;
            }
            const errDiv = getElement('ratingError');
            if (errDiv) errDiv.style.display = 'none';

            // غیرفعال کردن دکمه ثبت
            const submitBtn = getElement('submitReviewBtn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> در حال ثبت...';
            }

            // ارسال درخواست
            const formData = new FormData(reviewForm);
            const url = window.isEditing ? editUrl : submitUrl;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('HTTP error ' + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (data.success) {
                        showMessage('reviewMessage', data.message, 'success');
                        setTimeout(function () {
                            if (reviewModal) reviewModal.hide();
                            window.location.reload();
                        }, 1500);
                    } else {
                        showMessage('reviewMessage', data.message, 'error');
                        if (submitBtn) {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = window.isEditing ?
                                '<i class="fi-save ms-1"></i> ویرایش نظر' :
                                '<i class="fi-send ms-1"></i> ثبت نظر';
                        }
                    }
                })
                .catch(function (error) {
                    console.error('Fetch error:', error);
                    showMessage('reviewMessage', 'خطا در ارتباط با سرور: ' + error.message, 'error');
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = window.isEditing ?
                            '<i class="fi-save ms-1"></i> ویرایش نظر' :
                            '<i class="fi-send ms-1"></i> ثبت نظر';
                    }
                });
        });
    }

    // ============================================================
    // ۹. دکمه‌های ویرایش نظر (داینامیک)
    // ============================================================
    function bindEditButtons() {
        document.querySelectorAll('.edit-review-btn').forEach(function (btn) {
            // حذف listener قبلی
            if (btn._listener) {
                btn.removeEventListener('click', btn._listener);
            }

            const listener = function (e) {
                e.preventDefault();

                const reviewId = this.dataset.reviewId;
                const oldRating = parseInt(this.dataset.rating, 10) || 0;
                const oldComment = this.dataset.comment || '';
                const orderName = this.dataset.orderName || 'نظر عمومی';

                // نمایش اطلاعات سفارش
                const infoDiv = getElement('reviewOrderInfo');
                const nameSpan = getElement('orderNameDisplay');
                if (infoDiv && nameSpan) {
                    nameSpan.innerText = orderName;
                    infoDiv.style.display = 'block';
                }

                // مخفی کردن بخش انتخاب سفارش
                const section = getElement('orderSelectionSection');
                if (section) section.style.display = 'none';

                // تنظیم ستاره‌ها
                stars.forEach(function (star) {
                    const val = parseInt(star.dataset.value, 10);
                    if (val <= oldRating) {
                        star.classList.add('active');
                    } else {
                        star.classList.remove('active');
                    }
                });

                ratingInput.value = oldRating;

                // تنظیم متن نظر
                const commentField = getElement('reviewComment');
                if (commentField) commentField.value = oldComment;

                // تنظیم ID نظر برای ویرایش
                const orderIdField = getElement('reviewOrderId');
                if (orderIdField) {
                    orderIdField.name = 'review_id';
                    orderIdField.value = reviewId;
                }

                // تغییر دکمه ثبت
                const submitBtn = getElement('submitReviewBtn');
                if (submitBtn) {
                    submitBtn.innerHTML = '<i class="fi-save ms-1"></i> ویرایش نظر';
                }

                window.isEditing = true;
                window.editingReviewId = reviewId;

                if (reviewModal) reviewModal.show();
            };

            btn.addEventListener('click', listener);
            btn._listener = listener;
        });
    }

    // ============================================================
    // ۱۰. اجرای اولیه
    // ============================================================
    bindEditButtons();

    // برای مواردی که محتوای داینامیک اضافه میشه
    if (window.MutationObserver) {
        const observer = new MutationObserver(function () {
            bindEditButtons();
        });

        const reviewsContainer = document.querySelector('.reviews-container-scroll');
        if (reviewsContainer) {
            observer.observe(reviewsContainer, {
                childList: true,
                subtree: true
            });
        }
    }

    // صادر کردن برای استفاده در صورت نیاز
    window.ReviewSystem = {
        resetForm: resetForm,
        bindEditButtons: bindEditButtons,
        showMessage: showMessage
    };
})();