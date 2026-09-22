/* Only a generic, public offline document is stored. No runtime caching. */
'use strict';
const CACHE_PREFIX = 'winjob-pwa-offline-';
const CACHE_NAME = CACHE_PREFIX + '__PWA_VERSION__';
const OFFLINE_URL = '{{ offline_url|escapejs }}';

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const response = await fetch(OFFLINE_URL, {cache: 'reload', credentials: 'omit'});
        if (!response.ok || response.redirected ||
            !response.headers.get('content-type')?.includes('text/html')) {
            throw new Error('WinJob offline document could not be installed');
        }
        const cache = await caches.open(CACHE_NAME);
        await cache.put(OFFLINE_URL, response);
    })());
    // Updates wait until all tabs close. Never reload an open payment/form.
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const keys = await caches.keys();
        await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map(key => caches.delete(key)));
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin ||
        request.mode !== 'navigate') return;
    // Payment callbacks, logout and admin must retain native network semantics.
    if (/^\/(?:payment|gateway|admin)(?:\/|$)/.test(url.pathname) ||
        url.pathname === '/accounts/logout/') return;
    event.respondWith((async () => {
        try {
            // Do not store HTML, authentication state, API responses or error pages.
            return await fetch(request, {cache: 'no-store'});
        } catch (error) {
            const cached = await (await caches.open(CACHE_NAME)).match(OFFLINE_URL);
            return cached || new Response('اتصال برقرار نیست. دوباره تلاش کنید.', {
                status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}
            });
        }
    })());
});
