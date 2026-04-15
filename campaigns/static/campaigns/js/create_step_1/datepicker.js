"use strict";

window.initDatepicker = function () {

    $(function () {

        var todayUnix = (new persianDate()).unix() * 1000;

        var initialStart = $("#id_start_date").val();
        var initialEnd = $("#id_end_date").val();

        $(".range-to").persianDatepicker({

            initialValue: false,
            format: "YYYY/MM/DD HH:mm",
            minDate: todayUnix,

            timePicker: {
                enabled: true,
                meridiem: { enabled: false }
            },

            onSelect: function (unix) {

                var formatted = new persianDate(unix).format("YYYY/MM/DD HH:mm");

                $("#id_end_date").val(formatted);
                $(".range-to").val(formatted);

            }

        });

        $(".range-from").persianDatepicker({

            initialValue: false,
            format: "YYYY/MM/DD HH:mm",
            minDate: todayUnix,

            timePicker: {
                enabled: true,
                meridiem: { enabled: false }
            },

            onSelect: function (unix) {

                var formatted = new persianDate(unix).format("YYYY/MM/DD HH:mm");

                $("#id_start_date").val(formatted);
                $(".range-from").val(formatted);

            }

        });

        if (initialStart) $(".range-from").val(initialStart);
        if (initialEnd) $(".range-to").val(initialEnd);

    });

};
