"""Run independently: python tests/test_pwa.py (no DB, bot token or payment calls)."""
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from django.conf import settings
if not settings.configured:
    settings.configure(
        SECRET_KEY='pwa-tests-only', ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'],
        INSTALLED_APPS=['django.contrib.staticfiles'], STATIC_URL='/static/',
        STATICFILES_DIRS=[ROOT / 'static'],
        TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'DIRS': [ROOT / 'templates']}],
    )
import django
django.setup()
from django.test import SimpleTestCase
from django.urls import path
from django.template.loader import render_to_string
from core import pwa

urlpatterns = [
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('service-worker.js', pwa.service_worker, name='pwa_service_worker'),
    path('offline/', pwa.offline, name='pwa_offline'),
]


class PWATests(SimpleTestCase):
    def test_public_endpoints_and_methods(self):
        for url in ['/manifest.webmanifest', '/service-worker.js', '/offline/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.head(url).status_code, 200)
                self.assertEqual(self.client.post(url).status_code, 405)
                self.assertFalse(self.client.get(url).cookies)

    def test_manifest_and_real_icons(self):
        import struct
        r = self.client.get('/manifest.webmanifest')
        self.assertEqual(r['Content-Type'], 'application/manifest+json')
        data = r.json()
        self.assertEqual((data['id'], data['scope'], data['start_url']), ('/', '/', '/'))
        self.assertEqual((data['lang'], data['dir'], data['display']), ('fa', 'rtl', 'standalone'))
        for icon in data['icons']:
            raw = (ROOT / icon['src'].lstrip('/')).read_bytes()
            self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
            width, height = struct.unpack('>II', raw[16:24])
            self.assertEqual(icon['sizes'], f'{width}x{height}')

    def test_worker_headers_and_version_change(self):
        response = self.client.get('/service-worker.js')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('application/javascript', response['Content-Type'])
        self.assertNotIn(b'__PWA_VERSION__', response.content)
        original = pwa.render_to_string
        def changed(name, *args, **kwargs):
            return original(name, *args, **kwargs) + ('<!-- changed -->' if name.endswith('offline.html') else '')
        with patch.object(pwa, 'render_to_string', side_effect=changed):
            self.assertNotEqual(response.content, self.client.get('/service-worker.js').content)

    def test_offline_document_has_no_user_context_or_external_dependencies(self):
        self.client.cookies['sessionid'] = 'private-test-session'
        body = self.client.get('/offline/').content.decode()
        self.assertNotIn('private-test-session', body)
        self.assertNotIn('<script', body)
        self.assertNotIn('src=', body)
        self.assertNotIn('<link', body)
        self.assertIn('href=""', body)

    def test_head_resolves_real_routes(self):
        html = render_to_string('pwa/head.html')
        self.assertIn('href="/manifest.webmanifest"', html)
        self.assertIn('data-worker-url="/service-worker.js"', html)
        self.assertIn('/static/pwa/icons/apple-touch-icon.png', html)


if __name__ == '__main__':
    import unittest
    unittest.main()
