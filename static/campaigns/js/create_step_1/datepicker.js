"use strict";

window.initDatepicker = function () {
    console.log("🔥 initDatepicker called");
    var today = new persianDate().startOf('day');
    var todayUnix = today.unix() * 1000;
    var minDaysAfterStart = 2;
    var maxDaysAfterStart = 14;

    var $startHidden = $("#id_start_date");
    var $endHidden = $("#id_end_date");
    var $startPicker = $(".range-from");
    var $endPicker = $(".range-to");
    var startPickerInstance = null;
    var endPickerInstance = null;

    // تابع کمکی برای ساخت دیت‌پیکر پایان با محدودیت بر اساس startUnix
    function setupEndPicker(startUnix, selectedEndUnix) {
        if (!startUnix) return;

        var minEndUnix = startUnix + (minDaysAfterStart * 24 * 60 * 60 * 1000);
        var maxEndUnix = startUnix + (maxDaysAfterStart * 24 * 60 * 60 * 1000);

        if (endPickerInstance) {
            endPickerInstance.destroy();
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
        endPickerInstance = $endPicker.data("datepicker");

        if (selectedEndUnix && selectedEndUnix >= minEndUnix && selectedEndUnix <= maxEndUnix) {
            var formattedEnd = new persianDate(selectedEndUnix).format("YYYY/MM/DD");
            $endPicker.val(formattedEnd);
        } else {
            $endPicker.val("");
            $endHidden.val("");
        }
    }

    // تابع بازسازی دیت‌پیکر پایان بعد از انتخاب تاریخ شروع
    function updateEndPickerOnStartSelect(startUnix) {
        var minEndUnix = startUnix + (minDaysAfterStart * 24 * 60 * 60 * 1000);
        var maxEndUnix = startUnix + (maxDaysAfterStart * 24 * 60 * 60 * 1000);

        if (endPickerInstance) {
            endPickerInstance.destroy();
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
                if (window.validateForm) window.validateForm();
            }
        });
        endPickerInstance = $endPicker.data("datepicker");
        $endHidden.val("");
        $endPicker.val("");
    }

    // متد اصلی برای تنظیم حداقل روزهای مجاز برای تاریخ شروع
    function setStartMinDays(daysOffset) {
    // جبران offset برای نمایش صحیح در persian-datepicker
    var actualOffset = daysOffset - 1;
    var todayClean = new persianDate().startOf('day');
    var minDateUnix = new persianDate(todayClean).add('days', actualOffset).unix() * 1000;

    // از بین بردن دیت‌پیکرهای قبلی
    if (startPickerInstance) startPickerInstance.destroy();
    if (endPickerInstance) endPickerInstance.destroy();

    // بررسی اینکه آیا مقدار قبلی تاریخ شروع معتبر هست یا نه
    var prevStartStr = $startHidden.val();
    var prevStartUnix = prevStartStr ? new persianDate(prevStartStr).unix() * 1000 : null;
    var validStart = prevStartUnix && prevStartUnix >= minDateUnix;

    // اگر معتبر نیست، پاکش کن
    if (!validStart) {
        $startHidden.val("");
        $startPicker.val("");
        $endHidden.val("");
        $endPicker.val("");
    } else {
        $startPicker.val(prevStartStr);
    }

    // ساخت دیت‌پیکر شروع با محدودیت جدید
    $startPicker.persianDatepicker({
        format: "YYYY/MM/DD",
        minDate: minDateUnix,
        initialValue: validStart ? prevStartUnix : false,
        timePicker: { enabled: false },
        onSelect: function (unix) {
            var formatted = new persianDate(unix).format("YYYY/MM/DD");
            $startHidden.val(formatted);
            $startPicker.val(formatted);
            updateEndPickerOnStartSelect(unix);
            if (window.validateForm) window.validateForm();
        }
    });
    startPickerInstance = $startPicker.data("datepicker");

    if (validStart) {
        var prevEndStr = $endHidden.val();
        var prevEndUnix = prevEndStr ? new persianDate(prevEndStr).unix() * 1000 : null;
        setupEndPicker(prevStartUnix, prevEndUnix);
    }
}

    // در ابتدا با offSet پیش‌فرض ۲ روزه اجرا کن
    setStartMinDays(2);

    // شئ سراسری برای دسترسی از بیرون
    window.CampaignDatepicker = {
        setStartMinDays: setStartMinDays
    };
};