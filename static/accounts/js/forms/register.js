document.addEventListener('DOMContentLoaded', function () {
    const roleSelect = document.getElementById('role-select');
    const teamWrapper = document.getElementById('team-fields-wrapper');
    const createNewTeamCheckbox = document.getElementById('create-new-team');
    const teamSlugField = document.getElementById('team-slug-field');
    const teamNameField = document.getElementById('team-name-field');

    function toggleTeamFields() {
        if (roleSelect.value === 'team_member') {
            teamWrapper.style.display = 'block';
            toggleTeamSlugVsName();
        } else {
            teamWrapper.style.display = 'none';
        }
    }

    function toggleTeamSlugVsName() {
        if (createNewTeamCheckbox && createNewTeamCheckbox.checked) {
            teamSlugField.style.display = 'none';
            teamNameField.style.display = 'block';
        } else {
            teamSlugField.style.display = 'block';
            teamNameField.style.display = 'none';
        }
    }

    if (roleSelect) {
        roleSelect.addEventListener('change', toggleTeamFields);
    }

    if (createNewTeamCheckbox) {
        createNewTeamCheckbox.addEventListener('change', toggleTeamSlugVsName);
    }

    toggleTeamFields();
});
