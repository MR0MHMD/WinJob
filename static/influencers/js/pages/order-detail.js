function copyToClipboard(elementId, buttonElement) {
    const element = document.getElementById(elementId);
    let textToCopy = '';

    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        textToCopy = element.value;
        element.select();
        element.setSelectionRange(0, 99999);
    } else {
        textToCopy = element.innerText;
        const textarea = document.createElement('textarea');
        textarea.value = textToCopy;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        return showToast(buttonElement);
    }

    document.execCommand('copy');
    showToast(buttonElement);
}

function showToast(buttonElement) {
    const originalHtml = buttonElement.innerHTML;
    buttonElement.innerHTML = '<i class="fi-check"></i> کپی شد!';
    setTimeout(() => {
        buttonElement.innerHTML = originalHtml;
    }, 1500);

    const toast = document.getElementById('copyToast');
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 1500);
}

function shareLink(url) {
    if (navigator.share) {
        navigator.share({
            title: 'لینک تبلیغ',
            url: url
        }).catch(() => {
        });
    } else {
        copyToClipboard('destinationLink', event.target);
    }
}

const copyLinkBtn = document.querySelector('.copy-link-btn');
if (copyLinkBtn) {
    copyLinkBtn.onclick = function () {
        const input = document.getElementById('trackingLink');
        input.select();
        input.setSelectionRange(0, 99999);
        document.execCommand('copy');
        showToast(this);
    };
}

const confirmRejectBtn = document.getElementById('confirmRejectBtn');
    const rejectForm = document.getElementById('rejectForm');

    if (confirmRejectBtn && rejectForm) {
        confirmRejectBtn.addEventListener('click', function() {
            const modal = bootstrap.Modal.getInstance(document.getElementById('rejectModal'));
            modal.hide();
            rejectForm.submit();
        });
    }