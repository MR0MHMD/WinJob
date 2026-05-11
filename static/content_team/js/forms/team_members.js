function populateEditForm(memberId, role, percent) {
    document.getElementById('edit_member_id').value = memberId;
    document.getElementById('edit_role').value = role;
    document.getElementById('edit_percent').value = percent;
}

function showDeactivateModal(memberId, memberName) {
    document.getElementById('deactivate_member_id').value = memberId;
    document.getElementById('deactivate_member_name').innerText = memberName;
    new bootstrap.Modal(document.getElementById('deactivateMemberModal')).show();
}

function showExpelModal(memberId, memberName) {
    document.getElementById('expel_member_id').value = memberId;
    document.getElementById('expel_member_name').innerText = memberName;
    new bootstrap.Modal(document.getElementById('expelMemberModal')).show();
}

function copyInviteCode() {
    const codeElement = document.querySelector('.code');
    const code = codeElement ? codeElement.textContent.trim() : '';

    navigator.clipboard.writeText(code).then(function () {
        const btn = document.getElementById('copyInviteCodeBtn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fi-check-circle me-1"></i> کپی شد!';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-success');

        setTimeout(function () {
            btn.innerHTML = originalHtml;
            btn.classList.remove('btn-success');
            btn.classList.add('btn-primary');
        }, 2000);
    }).catch(function () {
        const textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);

        const btn = document.getElementById('copyInviteCodeBtn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fi-check-circle me-1"></i> کپی شد!';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-success');

        setTimeout(function () {
            btn.innerHTML = originalHtml;
            btn.classList.remove('btn-success');
            btn.classList.add('btn-primary');
        }, 2000);
    });
}

function populateEditForm(memberId, role, percent) {
    document.getElementById('edit_member_id').value = memberId;
    document.getElementById('edit_role').value = role;
    document.getElementById('edit_percent').value = percent;
}

function showRemoveModal(memberId, memberName) {
    document.getElementById('remove_member_id').value = memberId;
    document.getElementById('remove_member_name').innerText = memberName;
    new bootstrap.Modal(document.getElementById('removeMemberModal')).show();
}

function showApproveModal(teamSlug, requestId, memberName) {
    const form = document.getElementById('approveForm');
    form.action = `/content_team/team/${teamSlug}/requests/${requestId}/handle/`;
    document.getElementById('approve_member_name').innerText = memberName;
    new bootstrap.Modal(document.getElementById('confirmApproveModal')).show();
}

function showRejectModal(teamSlug, requestId, memberName) {
    const form = document.getElementById('rejectForm');
    form.action = `/content_team/team/${teamSlug}/requests/${requestId}/handle/`;
    document.getElementById('reject_member_name').innerText = memberName;
    new bootstrap.Modal(document.getElementById('confirmRejectModal')).show();
}