(function () {

    'use strict';


    var boot = function () {
        var preloader =
            document.querySelector('.page-loading');

        if (!preloader) {
            return;
        }

        var progress =
            preloader.querySelector(
                '[data-loader-progress]'
            );

        var percent =
            preloader.querySelector(
                '[data-loader-percent]'
            );

        var animationDuration = 1000;
        var pageLoaded = false;
        var animationFinished = false;
        var isClosing = false;

        var setProgress = function (value) {
            if (progress) {
                progress.style.width =
                    value + '%';
            }


            if (percent) {
                percent.textContent =
                    String(value)
                        .padStart(3, '0') + '%';
            }
        };

        preloader.classList.add('active');
        var startTime = Date.now();
        var progressAnimation =
            window.setInterval(function () {
                if (animationFinished) {
                    window.clearInterval(
                        progressAnimation
                    );
                    return;
                }

                var elapsed =
                    Date.now() - startTime;

                var ratio =
                    Math.min(
                        elapsed /
                        animationDuration,
                        1
                    );

                var eased =
                    1 -
                    Math.pow(
                        1 - ratio,
                        2
                    );

                var value =
                    Math.floor(
                        eased * 92
                    );
                setProgress(value);

                if (
                    elapsed >=
                    animationDuration
                ) {
                    window.clearInterval(
                        progressAnimation
                    );
                    animationFinished =
                        true;
                    setProgress(92);
                    tryToClose();
                }
            }, 16);

        function tryToClose() {

            if (
                isClosing ||
                !animationFinished ||
                !pageLoaded
            ) {
                return;
            }
            isClosing = true;

            setProgress(100);

            preloader.classList.add(
                'complete'
            );

            window.setTimeout(function () {
                preloader.classList.add(
                    'is-closing'
                );
            }, 90);

            window.setTimeout(function () {
                if (
                    preloader &&
                    preloader.parentNode
                ) {
                    preloader.parentNode
                        .removeChild(
                            preloader
                        );
                }
            }, 420);
        }

        if (
            document.readyState ===
            'complete'
        ) {
            pageLoaded = true;
            tryToClose();
        } else {
            window.addEventListener(
                'load',
                function () {
                    pageLoaded = true;
                    tryToClose();
                },
                {
                    once: true
                }
            );
        }
        window.setTimeout(function () {
            if (!pageLoaded) {
                pageLoaded = true;
                tryToClose();
            }
        }, 8000);
    };

    if (
        document.readyState ===
        'loading'
    ) {
        document.addEventListener(
            'DOMContentLoaded',
            boot,
            {
                once: true
            }
        );
    } else {
        boot();
    }
})();