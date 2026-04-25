function submitProfileForm(formSelector, url, successMessage) {

    $(formSelector).submit(function(event) {
        event.preventDefault();

        let formData = new FormData(this);

        $.ajax({
            type: "POST",
            url: url,
            data: formData,
            processData: false,
            contentType: false,

            success: function(response) {

                if (response.status === "success") {

                    $("#alert-container").html(
                        '<div class="alert alert-success alert-dismissible fade show" role="alert">' +
                        '<span class="fw-bold">موفق: </span>' + successMessage +
                        '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' +
                        '</div>'
                    );

                } else {

                    console.log(response.message);

                    $("#alert-container").html(
                        '<div class="alert alert-danger alert-dismissible fade show" role="alert">' +
                        '<span class="fw-bold">خطا:</span> ' + JSON.stringify(response.message) +
                        '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' +
                        '</div>'
                    );

                }
            },

            error: function(xhr) {

                console.log(xhr.responseText);

                $("#alert-container").html(
                    '<div class="alert alert-danger alert-dismissible fade show" role="alert">' +
                    '<span class="fw-bold">خطا:</span> ارتباط با سرور برقرار نشد.' +
                    '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' +
                    '</div>'
                );
            }
        });

    });

}


/* -------------------------
   اتصال فرم‌ها
------------------------- */

submitProfileForm(
    "#user",
    "/accounts/update/",
    "اطلاعات شما با موفقیت ذخیره شد"
);

submitProfileForm(
    "#advertiser",
    "/advertisers/update/",
    "اطلاعات پروفایل کسب‌وکار با موفقیت ذخیره شد"
);

submitProfileForm(
    "#influencer",
    "/influencers/update/",
    "اطلاعات پروفایل اینفلوئنسر با موفقیت ذخیره شد"
);


/* -------------------------
   تنظیمات FilePond
------------------------- */

FilePond.setOptions({
    storeAsFile: true
});

FilePond.parse(document.body);

document.addEventListener('DOMContentLoaded', function() {
    const shebaInput = document.getElementById('sheba-input');

    if (!shebaInput) return;

    function cleanSheba(value) {
        // حذف IR و هر چیز غیر عدد
        let cleaned = value.replace(/IR\s*-\s*/gi, '');
        cleaned = cleaned.replace(/IR/gi, '');
        cleaned = cleaned.replace(/[^0-9]/g, '');

        // فقط 24 رقم اول رو نگه دار
        if (cleaned.length > 24) {
            cleaned = cleaned.slice(0, 24);
        }

        return cleaned;
    }

    function handleInput(e) {
        const rawValue = e.target.value;
        const cleaned = cleanSheba(rawValue);

        if (rawValue !== cleaned) {
            e.target.value = cleaned;
        }
    }

    function handlePaste(e) {
        e.preventDefault();

        const pastedData = (e.clipboardData || window.clipboardData).getData('text');

        shebaInput.value = cleanSheba(pastedData);

        const event = new Event('input', { bubbles: true });
        shebaInput.dispatchEvent(event);
    }

    shebaInput.addEventListener('keydown', function(e) {
        const currentLength = shebaInput.value.length;
        if (currentLength >= 24 &&
            e.key >= '0' && e.key <= '9' &&
            e.key !== 'Backspace' &&
            e.key !== 'Delete' &&
            e.key !== 'Tab' &&
            e.key !== 'ArrowLeft' &&
            e.key !== 'ArrowRight' &&
            e.key !== 'ArrowUp' &&
            e.key !== 'ArrowDown') {
            e.preventDefault();
        }
    });

    shebaInput.addEventListener('input', handleInput);
    shebaInput.addEventListener('paste', handlePaste);
});