(function () {

    "use strict";

    window.initAttachments = function () {

        window.attachments = window.attachments || [];

        const MAX_FILES = 5;

        const modalFileInput = document.getElementById("modal-file-input");
        const modalDescription = document.getElementById("modal-file-description");

        const saveFileBtn = document.getElementById("save-file-btn");

        const attachmentsList = document.getElementById("attachments-list");

        const hiddenInput = document.getElementById("attachments-input");
        const hiddenDescriptions = document.getElementById("attachment-descriptions");

        const deletedInput = document.getElementById("deleted-attachments");

        const attachmentsTable = document.getElementById("attachments-table");

        const tableHead = attachmentsTable.querySelector("thead");

        const deletedIds = [];

        function formatFileSize(bytes) {

            const toFa = n => n.toLocaleString("fa-IR");

            if (bytes < 1024) return toFa(bytes) + " بایت";

            if (bytes < 1024 * 1024)
                return toFa((bytes / 1024).toFixed(1)) + " کیلوبایت";

            return toFa((bytes / (1024 * 1024)).toFixed(1)) + " مگابایت";

        }

        function updateTableHead() {

            const existingRows = attachmentsList.querySelectorAll("tr[data-existing]");

            if (existingRows.length === 0 && attachments.length === 0)
                tableHead.style.display = "none";
            else
                tableHead.style.display = "table-header-group";

        }

        function renderAttachments() {

            attachmentsList
                .querySelectorAll("tr[data-new]")
                .forEach(el => el.remove());

            const dataTransfer = new DataTransfer();

            const descList = [];

            attachments.forEach((item, index) => {

                const file = item.file;

                const isImage = file.type.startsWith("image/");

                const fileSize = formatFileSize(file.size);

                const fileType = file.type || "Unknown";

                const preview = isImage
                    ? `<img src="${URL.createObjectURL(file)}"
style="width:55px;height:55px;object-fit:cover;border-radius:6px;">`
                    : `<span class="text-secondary">—</span>`;

                const url = URL.createObjectURL(file);

                const tr = document.createElement("tr");

                tr.setAttribute("data-new", "true");

                tr.innerHTML =
                    `<td>
                        ${preview}
                    </td>
                        
                     <td class="text-light">
                         <a href="${url}" target="_blank" class="text-decoration-none text-light">
                             ${file.name}
                         </a>
                     </td>
                    
                     <td class="text-secondary">
                        ${fileType}
                     </td>
                    
                     <td class="text-info">
                         ${fileSize}
                     </td>
                     
                     <td>
                         <span class="text-danger fs-4" style="cursor:pointer" data-index="${index}">&times;</span>
                     </td>`;

                attachmentsList.appendChild(tr);

                dataTransfer.items.add(file);

                descList.push(item.description);

            });

            hiddenInput.files = dataTransfer.files;

            hiddenDescriptions.value = JSON.stringify(descList);

            updateTableHead();

        }

        attachmentsList.addEventListener("click", function (e) {

            if (e.target.dataset.index) {

                const index = e.target.dataset.index;

                attachments.splice(index, 1);

                renderAttachments();

            }

            if (e.target.classList.contains("remove-existing-file")) {

                const id = e.target.dataset.id;

                deletedIds.push(id);

                deletedInput.value = JSON.stringify(deletedIds);

                e.target.closest("tr").remove();

                updateTableHead();

            }

        });

        saveFileBtn.addEventListener("click", function () {

            const file = modalFileInput.files[0];

            const description = modalDescription.value.trim();

            if (!file) {
                alert("لطفاً یک فایل انتخاب کنید");
                return;
            }

            if (attachments.length >= MAX_FILES) {
                alert("حداکثر ۵ فایل می‌توانید اضافه کنید");
                return;
            }

            attachments.push({file, description});

            renderAttachments();

            modalFileInput.value = "";

            modalDescription.value = "";

            document.getElementById("fileList").innerHTML = "";

            const modal = bootstrap.Modal.getInstance(
                document.getElementById("attachmentsModal")
            );

            modal.hide();

        });

        updateTableHead();

    };

})();
