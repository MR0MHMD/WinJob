function initPaymentSystem() {
    const paymentOptions = document.querySelectorAll('.payment-option');
    const paymentMethodInput = document.getElementById('payment-method-input');
    const form = document.getElementById('step4-form');
    const submitBtn = document.getElementById('pay-submit-btn');

    if (!paymentOptions.length || !paymentMethodInput) return;

    // انتخاب روش پرداخت
    paymentOptions.forEach(opt => {
        opt.addEventListener('click', function() {
            if (this.classList.contains('disabled')) return;

            paymentOptions.forEach(o => o.classList.remove('active'));
            this.classList.add('active');
            paymentMethodInput.value = this.dataset.method;
        });
    });

    // ارسال فرم
    if (form && submitBtn) {
        submitBtn.addEventListener('click', function(e) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'در حال پردازش...';
            form.submit();
        });
    }
}