const overlay = document.getElementById("confirm-overlay");
const confirmChannelName = document.getElementById("confirm-channel-name");
const confirmDeleteBtn = document.getElementById("confirm-delete");
const cancelBtn = document.getElementById("confirm-cancel");

let deleteId = null;

document.addEventListener("click", function (e) {

    if (e.target.classList.contains("delete-btn")) {

        deleteId = e.target.dataset.id;
        const name = e.target.dataset.name;

        confirmChannelName.innerText = name;

        overlay.classList.add("active");
    }

});


cancelBtn.addEventListener("click", function () {
    overlay.classList.remove("active");
});


confirmDeleteBtn.addEventListener("click", function () {

    if (!deleteId) return;

    const form = document.createElement("form");
    form.method = "POST";
    form.action = `/influencers/my_channels/delete/${deleteId}/`;

    const csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrfmiddlewaretoken";
    csrf.value = getCookie("csrftoken");

    form.appendChild(csrf);
    document.body.appendChild(form);

    form.submit();
});


function getCookie(name) {

    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {

        const cookies = document.cookie.split(";");

        for (let i = 0; i < cookies.length; i++) {

            const cookie = cookies[i].trim();

            if (cookie.substring(0, name.length + 1) === (name + "=")) {

                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;

            }
        }
    }

    return cookieValue;
}
