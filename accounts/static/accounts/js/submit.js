document.querySelector("#form_submit").addEventListener("click", function(event) {
    event.preventDefault();

    var activeTab = document.querySelector('.nav-link.active');
    if (activeTab) {
        var activeTabId = activeTab.getAttribute('href').substring(1);
        var formToSubmit = document.getElementById(activeTabId);

        if (formToSubmit) {
            console.log("Form found, attempting to submit...");

            formToSubmit.requestSubmit();
        } else {
            console.log("Form not found");
        }
    }
});