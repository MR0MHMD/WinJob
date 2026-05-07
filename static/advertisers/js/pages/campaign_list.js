document.addEventListener("DOMContentLoaded", function () {

    const filterItems = document.querySelectorAll(".filter-item");
    const campaignList = document.getElementById("campaign-list");

    filterItems.forEach(item => {

        item.addEventListener("click", function (e) {

            e.preventDefault();

            const url = this.getAttribute("href");

            fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
                .then(res => res.json())
                .then(data => {

                    campaignList.innerHTML = data.html;

                    filterItems.forEach(i => i.classList.remove("active"));
                    this.classList.add("active");

                    window.history.pushState({}, "", url);
                });
        });
    });
});