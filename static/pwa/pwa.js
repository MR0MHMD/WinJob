(() => {
    'use strict';
    const script = document.querySelector('script[data-winjob-pwa]');
    const install = document.querySelector('[data-pwa-install]');
    const help = document.querySelector('[data-pwa-help]');
    const offline = document.querySelector('[data-pwa-offline]');
    const update = document.querySelector('[data-pwa-update]');
    let promptEvent = null;
    const standalone = window.matchMedia('(display-mode: standalone)');
    const installed = () => standalone.matches || navigator.standalone === true;
    const refresh = () => {
        if (install) install.hidden = installed() || !promptEvent;
        if (help) help.hidden = installed();
        if (offline) offline.hidden = navigator.onLine;
    };
    window.addEventListener('beforeinstallprompt', event => {
        event.preventDefault();
        promptEvent = event;
        refresh();
    });
    window.addEventListener('appinstalled', () => {
        promptEvent = null;
        if (install) install.hidden = true;
        if (help) help.hidden = true;
    });
    standalone.addEventListener?.('change', refresh);
    window.addEventListener('online', refresh);
    window.addEventListener('offline', refresh);
    install?.addEventListener('click', async () => {
        if (!promptEvent) return;
        const currentPrompt = promptEvent;
        promptEvent = null;
        refresh();
        try {
            await currentPrompt.prompt();
            await currentPrompt.userChoice;
        } catch (error) {
            console.warn('WinJob installation prompt unavailable', error);
        }
    });
    refresh();
    if (!window.isSecureContext || !('serviceWorker' in navigator) || !script) return;
    navigator.serviceWorker.register(script.dataset.workerUrl, {
        scope: '/', updateViaCache: 'none'
    }).then(registration => {
        const showUpdate = () => {
            if (registration.waiting && navigator.serviceWorker.controller && update) {
                update.hidden = false;
            }
        };
        showUpdate();
        registration.addEventListener('updatefound', () => {
            registration.installing?.addEventListener('statechange', showUpdate);
        });
        // Checking does not activate a waiting worker or reload any open form.
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                registration.update().catch(() => {});
            }
        });
    }).catch(error => console.warn('WinJob PWA registration failed', error));
})();
