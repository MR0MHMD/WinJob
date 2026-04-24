const phoneNumber = document.getElementById('phone-number').innerText;
let timeLeft = 0;
let timerInterval = null;
let canResend = false;
let isResending = false;

const timerWrapper = document.getElementById('timerWrapper');
const resendWrapper = document.getElementById('resendWrapper');
const timerElement = document.getElementById('timer');
const resendBtn = document.getElementById('resend-btn');
const verifyBtn = document.getElementById('verify-btn');

const inputs = ['otp-1', 'otp-2', 'otp-3', 'otp-4', 'otp-5', 'otp-6'];
const otpInputs = inputs.map(id => document.getElementById(id));

function moveToNext(currentIndex) {
    if (currentIndex < 5) {
        otpInputs[currentIndex + 1].focus();
    }
}

function moveToPrev(currentIndex) {
    if (currentIndex > 0) {
        otpInputs[currentIndex - 1].focus();
    }
}

function clearError() {
    otpInputs.forEach(input => input.classList.remove('error'));
}

function showTimer() {
    timerWrapper.classList.remove('hide');
    resendWrapper.classList.add('hide');
}

function showResendButton() {
    timerWrapper.classList.add('hide');
    resendWrapper.classList.remove('hide');
}

otpInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
        e.target.value = e.target.value.replace(/[^0-9]/g, '');
        clearError();
        if (e.target.value.length === 1 && index < 5) {
            moveToNext(index);
        }
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && index > 0) {
            moveToPrev(index);
        }
    });

    input.addEventListener('paste', (e) => {
        e.preventDefault();
        clearError();
        const paste = (e.clipboardData || window.clipboardData).getData('text');
        const digits = paste.replace(/\D/g, '').split('').slice(0, 6);

        digits.forEach((digit, i) => {
            if (otpInputs[i]) {
                otpInputs[i].value = digit;
            }
        });

        if (digits.length === 6) {
            verifyBtn.focus();
        } else if (digits.length > 0) {
            otpInputs[Math.min(digits.length, 5)].focus();
        }
    });
});

async function fetchRemainingTime() {
    try {
        const response = await fetch('/accounts/api/check-phone/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                phone_number: phoneNumber,
                check_type: 'status'
            })
        });

        const data = await response.json();
        return data.remaining_time || 0;
    } catch (error) {
        console.error('Error fetching time:', error);
        return 0;
    }
}

function updateTimerDisplay() {
    if (timeLeft <= 0) {
        timerElement.innerHTML = '00:00';
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        canResend = true;
        showResendButton();
    } else {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        timerElement.innerHTML = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
}

function startTimer(initialTime) {
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    timeLeft = initialTime;

    if (timeLeft > 0) {
        showTimer();
        updateTimerDisplay();

        timerInterval = setInterval(() => {
            if (timeLeft > 0) {
                timeLeft--;
                updateTimerDisplay();
            } else {
                if (timerInterval) {
                    clearInterval(timerInterval);
                    timerInterval = null;
                }
                canResend = true;
                showResendButton();
            }
        }, 1000);
    } else {
        canResend = true;
        showResendButton();
    }
}

async function loadInitialTime() {
    const remaining = await fetchRemainingTime();
    if (remaining > 0) {
        startTimer(remaining);
        canResend = false;
    } else {
        startTimer(0);
        canResend = true;
    }
}

loadInitialTime()

resendBtn.addEventListener('click', async () => {
    if (!canResend || isResending) {
        if (!canResend) {
            showNotificationModal('توجه', 'لطفاً صبر کنید تا زمان ارسال مجدد کامل شود', 'warning');
        }
        return;
    }

    isResending = true;
    const originalText = resendBtn.innerHTML;
    resendBtn.innerHTML = '<i class="fi-arrow-repeat me-1 spinner"></i> در حال ارسال...';
    resendBtn.disabled = true;

    try {
        const response = await fetch('/accounts/api/resend-otp/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({phone_number: phoneNumber})
        });

        const data = await response.json();

        if (data.success) {
            showNotificationModal('کد جدید', 'کد تایید مجدداً برای شما ارسال شد', 'success');

            startTimer(data.remaining_time || 120);
            canResend = false;

            otpInputs.forEach(input => input.value = '');
            otpInputs[0].focus();
        } else {
            showNotificationModal('خطا', data.error || 'امکان ارسال مجدد وجود ندارد', 'error');

            if (data.remaining_time && data.remaining_time > 0) {
                startTimer(data.remaining_time);
                canResend = false;
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showNotificationModal('خطا', 'مشکلی در ارسال مجدد پیش آمد', 'error');
    } finally {
        isResending = false;
        resendBtn.innerHTML = originalText;
        if (!canResend) {
            resendBtn.disabled = false;
        }
    }
});

verifyBtn.addEventListener('click', async () => {
    const code = otpInputs.map(input => input.value).join('');

    if (code.length !== 6) {
        showNotificationModal('خطا', 'لطفاً کد ۶ رقمی را کامل وارد کنید', 'warning');
        otpInputs.forEach(input => input.classList.add('error'));
        setTimeout(clearError, 1000);
        return;
    }

    verifyBtn.classList.add('loading');
    verifyBtn.disabled = true;

    try {
        const response = await fetch('/accounts/api/verify-otp/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({code: code})
        });

        const data = await response.json();

        if (data.success) {
            if (timerInterval) {
                clearInterval(timerInterval);
            }
            showNotificationModal('تبریک!', data.message, 'success', () => {
                window.location.href = data.redirect_url;
            });
        } else {
            showNotificationModal('خطا', data.error, 'error');
            verifyBtn.classList.remove('loading');
            verifyBtn.disabled = false;

            otpInputs.forEach(input => {
                input.value = '';
                input.classList.add('error');
            });
            otpInputs[0].focus();
            setTimeout(clearError, 1000);
        }
    } catch (error) {
        console.error('Error:', error);
        showNotificationModal('خطا', 'مشکلی در ارتباط با سرور پیش آمد', 'error');
        verifyBtn.classList.remove('loading');
        verifyBtn.disabled = false;
    }
});

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
