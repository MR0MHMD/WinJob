"use strict";

window.initDatepicker = function () {

    $(function () {
        var today = new persianDate().startOf('day');
        var todayUnix = today.unix() * 1000;
        var minDaysAfterStart = 2;
        var maxDaysAfterStart = 14;

        // گرفتن مقادیر واقعی از hidden input‌ها (از سرور یا از داده‌های POST بعد از خطا)
        var $startHidden = $("#id_start_date");
        var $endHidden = $("#id_end_date");
        var initialStart = $startHidden.val();
        var initialEnd = $endHidden.val();

        var $startPicker = $(".range-from");
        var $endPicker = $(".range-to");

        // تابع برای مقداردهی دیت‌پیکر تاریخ پایان با محدودیت از startUnix
        function setupEndDatepickerWithConstraints(startUnix, selectedEndUnix) {
            if (!startUnix) return;

            var minEndUnix = startUnix + (minDaysAfterStart * 24 * 60 * 60 * 1000);
            var maxEndUnix = startUnix + (maxDaysAfterStart * 24 * 60 * 60 * 1000);

            if ($endPicker.data("datepicker")) {
                $endPicker.data("datepicker").destroy();
            }

            $endPicker.persianDatepicker({
                format: "YYYY/MM/DD",
                minDate: minEndUnix,
                maxDate: maxEndUnix,
                initialValue: false,
                timePicker: { enabled: false },
                onSelect: function (unix) {
                    var formatted = new persianDate(unix).format("YYYY/MM/DD");
                    $endHidden.val(formatted);
                    $endPicker.val(formatted);
                }
            });

            // اگر مقدار end_date از قبل وجود داشت و در بازه هست، ست کن
            if (selectedEndUnix && selectedEndUnix >= minEndUnix && selectedEndUnix <= maxEndUnix) {
                var formattedEnd = new persianDate(selectedEndUnix).format("YYYY/MM/DD");
                $endPicker.val(formattedEnd);
            } else {
                $endPicker.val("");
                $endHidden.val("");
            }
        }

        // تابع برای بروزرسانی دیت‌پیکر پایان بعد از انتخاب تاریخ شروع جدید
        function updateEndDatepickerOnStartSelect(startUnix) {
            var minEndUnix = startUnix + (minDaysAfterStart * 24 * 60 * 60 * 1000);
            var maxEndUnix = startUnix + (maxDaysAfterStart * 24 * 60 * 60 * 1000);

            if ($endPicker.data("datepicker")) {
                $endPicker.data("datepicker").destroy();
            }

            $endPicker.persianDatepicker({
                format: "YYYY/MM/DD",
                minDate: minEndUnix,
                maxDate: maxEndUnix,
                initialValue: false,
                timePicker: { enabled: false },
                onSelect: function (unix) {
                    var formatted = new persianDate(unix).format("YYYY/MM/DD");
                    $endHidden.val(formatted);
                    $endPicker.val(formatted);
                }
            });

            // پاک کردن مقدار قبلی end_date چون تاریخ شروع عوض شده
            $endHidden.val("");
            $endPicker.val("");
        }

        // مقداردهی دیت‌پیکر تاریخ شروع
        $startPicker.val(""); // پاک کردن مقدار نمایشی اولیه
        $startPicker.persianDatepicker({
            format: "YYYY/MM/DD",
            minDate: todayUnix,
            initialValue: false,
            timePicker: { enabled: false },
            onSelect: function (unix) {
                var formatted = new persianDate(unix).format("YYYY/MM/DD");
                $startHidden.val(formatted);
                $startPicker.val(formatted);
                updateEndDatepickerOnStartSelect(unix);
            }
        });

        // اگر start_date وجود دارد (از سرور یا بعد از خطا)
        if (initialStart) {
            var startUnix = new persianDate(initialStart).unix() * 1000;
            $startPicker.val(initialStart);
            // اگر end_date هم وجود دارد، مقدار یونیکس آن را محاسبه کن
            var endUnix = initialEnd ? new persianDate(initialEnd).unix() * 1000 : null;
            setupEndDatepickerWithConstraints(startUnix, endUnix);
        } else {
            // اگر start_date وجود ندارد، دیت‌پیکر پایان را به صورت ابتدایی با minDate امروز راه بینداز،
            // اما اجازه انتخاب نده تا وقتی start_date انتخاب شود (در onSelect چک میکنیم)
            $endPicker.persianDatepicker({
                format: "YYYY/MM/DD",
                minDate: todayUnix,
                initialValue: false,
                timePicker: { enabled: false },
                onSelect: function (unix) {
                    var startVal = $startHidden.val();
                    if (!startVal) {
                        alert("لطفاً ابتدا تاریخ شروع را انتخاب کنید.");
                        $endPicker.val("");
                        return;
                    }
                    var startUnix = new persianDate(startVal).unix() * 1000;
                    var minEndUnix = startUnix + (minDaysAfterStart * 24 * 60 * 60 * 1000);
                    var maxEndUnix = startUnix + (maxDaysAfterStart * 24 * 60 * 60 * 1000);
                    if (unix >= minEndUnix && unix <= maxEndUnix) {
                        var formatted = new persianDate(unix).format("YYYY/MM/DD");
                        $endHidden.val(formatted);
                        $endPicker.val(formatted);
                        // بعد از انتخاب، دیت‌پیکر را با محدودیت درست دوباره میسازیم
                        updateEndDatepickerOnStartSelect(startUnix);
                    } else {
                        alert("تاریخ پایان باید بین ۲ تا ۱۴ روز بعد از تاریخ شروع باشد.");
                        $endPicker.val("");
                    }
                }
            });
            // اگر start_date وجود نداشته باشد، مقدار end_date هم باید پاک شود
            $endHidden.val("");
            $endPicker.val("");
        }
    });
};