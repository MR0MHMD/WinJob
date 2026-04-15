document.querySelector('form.needs-validation').onsubmit = function (event) {
    event.preventDefault();

    var form = this;
    var formData = new FormData(form);

    fetch(form.action, {
        method: "POST",
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect_url;
            } else {
                alert(data.error);
            }
        })
        .catch(error => {
            console.error("Error:", error);
        });
}
