(function () {
    // قبول ویرایش
    document.querySelectorAll('.accept-revision-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const orderId = this.dataset.orderId;
            const revisionId = this.dataset.revisionId;
            const form = document.getElementById('acceptRevisionForm');
            form.action = `/content_team/orders/${orderId}/revision/${revisionId}/accept/`;
            document.getElementById('acceptRevisionId').value = revisionId;
        });
    });

    // رد ویرایش
    document.querySelectorAll('.reject-revision-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const orderId = this.dataset.orderId;
            const revisionId = this.dataset.revisionId;
            const form = document.getElementById('rejectRevisionForm');
            form.action = `/content_team/orders/${orderId}/revision/${revisionId}/reject/`;
            document.getElementById('rejectRevisionId').value = revisionId;
        });
    });

    // // مدیریت فرم رد سفارش (ارسال دلیل)
    // document.getElementById('rejectSubmitBtn')?.addEventListener('click', function (e) {
    //     const reason = document.getElementById('rejectReason').value;
    //     document.getElementById('rejectReasonInput').value = reason;
    // });
})();