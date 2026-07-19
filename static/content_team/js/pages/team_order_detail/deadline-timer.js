(function() {
    const deadlineTimer = document.getElementById('order-deadline-timer');
    if (deadlineTimer) {
        function updateDeadlineTimer() {
            const ts = deadlineTimer.getAttribute('data-deadline-timestamp');
            if (!ts) return;
            const deadline = parseInt(ts, 10);
            if (isNaN(deadline)) return;
            const now = Date.now();
            const remaining = deadline - now;
            const daysElem = deadlineTimer.querySelector('.days');
            const hoursElem = deadlineTimer.querySelector('.hours');
            const minsElem = deadlineTimer.querySelector('.minutes');
            const secsElem = deadlineTimer.querySelector('.seconds');

            if (remaining <= 0) {
                daysElem.textContent = '0';
                hoursElem.textContent = '0';
                minsElem.textContent = '0';
                secsElem.textContent = '0';
                deadlineTimer.classList.add('expired');
                deadlineTimer.classList.remove('status-green', 'status-yellow', 'status-red');
                return;
            }

            deadlineTimer.classList.remove('expired');
            const days = Math.floor(remaining / (1000 * 60 * 60 * 24));
            const hours = Math.floor((remaining % (86400000)) / (1000 * 60 * 60));
            const mins = Math.floor((remaining % (3600000)) / (1000 * 60));
            const secs = Math.floor((remaining % 60000) / 1000);

            daysElem.textContent = days;
            hoursElem.textContent = hours;
            minsElem.textContent = mins < 10 ? '0' + mins : mins;
            secsElem.textContent = secs < 10 ? '0' + secs : secs;

            const hoursRemaining = remaining / (1000 * 60 * 60);
            deadlineTimer.classList.remove('status-green', 'status-yellow', 'status-red');
            if (hoursRemaining > 72) deadlineTimer.classList.add('status-green');
            else if (hoursRemaining > 24) deadlineTimer.classList.add('status-yellow');
            else deadlineTimer.classList.add('status-red');
        }

        updateDeadlineTimer();
        setInterval(updateDeadlineTimer, 1000);
    }
})();