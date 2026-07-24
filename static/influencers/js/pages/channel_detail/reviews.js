// ==================== مدیریت مودال ثبت نظر ====================
document.addEventListener('DOMContentLoaded', function() {
    // داده‌های پویا از تمپلیت
    const config = window.channelReviewConfig || {};
    const canSubmitReview = config.canSubmitReview || false;
    const pendingBookingsCount = config.pendingBookingsCount || 0;
    const channelId = config.channelId || null;
    const csrfToken = config.csrfToken || '';
    const submitUrl = config.submitUrl || '';
    const editUrl = config.editUrl || '';
    const storageKey = `review_modal_closed_channel_${channelId}`;
    const urlParams = new URLSearchParams(window.location.search);
    const reviewParam = urlParams.get('review_booking_id');

    const reviewModalEl = document.getElementById('reviewModal');
    let reviewModal = null;
    if (reviewModalEl) {
        reviewModal = new bootstrap.Modal(reviewModalEl);
    }

    // نمایش خودکار مودال
    if (reviewParam && canSubmitReview) {
        setTimeout(() => { if (reviewModal) reviewModal.show(); }, 500);
    } else if (pendingBookingsCount > 0 && !sessionStorage.getItem(storageKey)) {
        setTimeout(() => { if (reviewModal) reviewModal.show(); }, 500);
    }

    // بسته شدن مودال
    if (reviewModalEl) {
        reviewModalEl.addEventListener('hidden.bs.modal', function () {
            if (!reviewParam) sessionStorage.setItem(storageKey, 'true');
            // ریست فرم
            document.getElementById('reviewForm').reset();
            document.getElementById('ratingValue').value = '';
            document.getElementById('reviewComment').value = '';
            document.getElementById('reviewBookingId').value = '';
            document.getElementById('submitReviewBtn').innerHTML = '<i class="fi-send ms-1"></i> ثبت نظر';
            window.isEditing = false;
            document.querySelectorAll('#starRatingInput i').forEach(s => s.classList.remove('active'));
            document.getElementById('reviewCampaignInfo').style.display = 'none';
            const section = document.getElementById('campaignSelectionSection');
            if (section) section.style.display = 'block';
        });
    }

    // دکمه دستی ثبت نظر
    const manualBtn = document.getElementById('manualReviewBtn');
    if (manualBtn && reviewModal && canSubmitReview) {
        manualBtn.addEventListener('click', function (e) {
            e.preventDefault();
            document.getElementById('reviewMessage').innerHTML = '';
            const section = document.getElementById('campaignSelectionSection');
            if (section) section.style.display = 'block';
            document.getElementById('reviewCampaignInfo').style.display = 'none';
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

    // ارسال فرم AJAX
    const reviewForm = document.getElementById('reviewForm');
    if (reviewForm) {
        reviewForm.addEventListener('submit', function (e) {
            e.preventDefault();

            if (!window.isEditing) {
                const selectedRadio = document.querySelector('input[name="selected_booking"]:checked');
                const bookingIdField = document.getElementById('reviewBookingId');
                if (bookingIdField) {
                    bookingIdField.value = selectedRadio ? selectedRadio.value : '';
                }
            }

            const rating = ratingInput.value;
            if (!rating) {
                document.getElementById('ratingError').style.display = 'block';
                return;
            }
            document.getElementById('ratingError').style.display = 'none';

            const submitBtn = document.getElementById('submitReviewBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> در حال ثبت...';

            const formData = new FormData(reviewForm);
            let url = submitUrl;
            if (window.isEditing) url = editUrl;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(response => {
                if (!response.ok) throw new Error('HTTP error ' + response.status);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    document.getElementById('reviewMessage').innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                    setTimeout(() => {
                        if (reviewModal) reviewModal.hide();
                        location.reload();
                    }, 2000);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = window.isEditing ? '<i class="fi-save ms-1"></i> ویرایش نظر' : '<i class="fi-send ms-1"></i> ثبت نظر';
                    document.getElementById('reviewMessage').innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                submitBtn.disabled = false;
                submitBtn.innerHTML = window.isEditing ? '<i class="fi-save ms-1"></i> ویرایش نظر' : '<i class="fi-send ms-1"></i> ثبت نظر';
                document.getElementById('reviewMessage').innerHTML = `<div class="alert alert-danger">خطا در ارتباط با سرور: ${error.message}</div>`;
            });
        });
    }

    // دکمه‌های ویرایش نظر
    function bindEditButtons() {
        document.querySelectorAll('.edit-review-btn').forEach(btn => {
            btn.removeEventListener('click', btn._listener);
            const listener = function (e) {
                e.preventDefault();
                const reviewId = this.dataset.reviewId;
                const oldRating = parseInt(this.dataset.rating);
                const oldComment = this.dataset.comment;
                let campaignName = this.dataset.campaignName;
                if (!campaignName) campaignName = 'نظر عمومی';

                const infoDiv = document.getElementById('reviewCampaignInfo');
                const nameSpan = document.getElementById('campaignNameDisplay');
                if (infoDiv && nameSpan) {
                    nameSpan.innerText = campaignName;
                    infoDiv.style.display = 'block';
                }
                const section = document.getElementById('campaignSelectionSection');
                if (section) section.style.display = 'none';

                stars.forEach(star => {
                    const val = parseInt(star.dataset.value);
                    if (val <= oldRating) star.classList.add('active');
                    else star.classList.remove('active');
                });
                ratingInput.value = oldRating;
                document.getElementById('reviewComment').value = oldComment;

                const bookingIdInput = document.getElementById('reviewBookingId');
                bookingIdInput.name = 'review_id';
                bookingIdInput.value = reviewId;
                document.getElementById('submitReviewBtn').innerHTML = '<i class="fi-save ms-1"></i> ویرایش نظر';
                window.isEditing = true;
                reviewModal.show();
            };
            btn.addEventListener('click', listener);
            btn._listener = listener;
        });
    }
    bindEditButtons();
});