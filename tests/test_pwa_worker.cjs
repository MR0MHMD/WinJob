// Node >=18: node tests/test_pwa_worker.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const handlers = {};
const saved = new Map();
const deleted = [];
let mode = 'online';
let claimed = false;
const cache = {
    put: async (key, response) => saved.set(key, response),
    match: async key => saved.get(key)?.clone(),
};
const context = {
    URL, Response, Promise, Error,
    self: {location: {origin: 'https://winjob.test'},
        addEventListener: (name, cb) => {handlers[name] = cb;},
        clients: {claim: async () => {claimed = true;}},
    },
    caches: {
        open: async () => cache,
        keys: async () => ['unrelated-app-cache', 'winjob-pwa-offline-old', 'winjob-pwa-offline-__PWA_VERSION__'],
        delete: async key => {deleted.push(key);},
    },
    fetch: async () => {
        if (mode === 'offline') throw new Error('network unavailable');
        if (mode === '500') return new Response('server error', {status: 500});
        if (mode === '404') return new Response('missing', {status: 404});
        return new Response('<html>public offline</html>', {headers: {'content-type': 'text/html'}});
    },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../templates/pwa/service-worker.js'),'utf8')
    .replace('{{ offline_url|escapejs }}', '/offline/'), context);
async function lifecycle(name) {
    let promise; handlers[name]({waitUntil: value => {promise=value;}}); await promise;
}
async function request(url, method='GET', requestMode='navigate') {
    let response;
    handlers.fetch({request: {url, method, mode: requestMode}, respondWith: value => {response=value;}});
    return response;
}
(async()=>{
    await lifecycle('install');
    assert.deepEqual([...saved.keys()], ['/offline/']);
    await lifecycle('activate');
    assert.ok(claimed);assert.deepEqual(deleted,['winjob-pwa-offline-old']);
    for (const route of ['/payment/callback/','/gateway/verify/','/admin/','/accounts/logout/']) {
        assert.equal(await request('https://winjob.test'+route),undefined);
    }
    assert.equal(await request('https://other.test/'),undefined);
    assert.equal(await request('https://winjob.test/api/','GET','cors'),undefined);
    assert.equal(await request('https://winjob.test/form/','POST'),undefined);
    assert.equal((await request('https://winjob.test/dashboard/')).status,200);
    for(const status of ['404','500']) {
        mode=status;assert.equal((await request('https://winjob.test/dashboard/')).status,Number(status));
    }
    mode='offline';
    assert.equal(await (await request('https://winjob.test/private/')).text(),'<html>public offline</html>');
    assert.deepEqual([...saved.keys()], ['/offline/']);
    saved.clear();assert.equal((await request('https://winjob.test/private/')).status,503);
    // Failed install cannot be accepted as a successful offline cache fill.
    mode='500';await assert.rejects(lifecycle('install'));
    console.log('PASS: offline fallback, cache isolation, payment/admin/logout bypass, non-GET/API/cross-origin bypass, HTTP error preservation, failed install.');
})().catch(error=>{console.error(error);process.exitCode=1;});
