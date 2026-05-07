(function () {

    "use strict";

    window.initUploadDragDrop = function () {

        const uploadBox = document.getElementById("fileUploadBox");
        const fileInput = document.getElementById("modal-file-input");
        const fileList = document.getElementById("fileList");

        if (!uploadBox || !fileInput || !fileList) return;

        function renderFiles(files) {

            fileList.innerHTML = "";

            Array.from(files).forEach(file => {

                const item = document.createElement("div");

                item.className = "file-item";

                item.innerHTML =
                    `<div class="file-item-name">${file.name}</div><div class="file-remove">✕</div>`;

                fileList.appendChild(item);

            });

        }

        uploadBox.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", function () {
            renderFiles(this.files);
        });

        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            uploadBox.addEventListener(eventName, function (e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        ["dragenter", "dragover"].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => {
                uploadBox.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => {
                uploadBox.classList.remove("dragover");
            });
        });

        uploadBox.addEventListener("drop", function (e) {

            const files = e.dataTransfer.files;

            fileInput.files = files;

            renderFiles(files);

        });

    };

})();
