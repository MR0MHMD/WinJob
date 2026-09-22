"""Public PWA metadata; deliberately independent of user/session context."""
import hashlib
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@require_safe
def manifest(request):
    response = JsonResponse({
        'id': '/', 'name': 'وینجاب | WinJob', 'short_name': 'وینجاب',
        'description': 'مدیریت تبلیغات و همکاری با ناشران در وینجاب',
        'lang': 'fa', 'dir': 'rtl', 'start_url': '/', 'scope': '/',
        'display': 'standalone', 'background_color': '#1f1b2d',
        'theme_color': '#1f1b2d',
        'screenshots': [
            {
                'src': static('pwa/screenshots/desktop-home.png'),
                'sizes': '1280x720',
                'type': 'image/png',
                'form_factor': 'wide',
                'label': 'صفحه اصلی وینجاب در رایانه',
            },
            {
                'src': static('pwa/screenshots/desktop-dashboard.png'),
                'sizes': '1280x720',
                'type': 'image/png',
                'form_factor': 'wide',
                'label': 'داشبورد مدیریت وینجاب در رایانه',
            },
            {
                'src': static('pwa/screenshots/mobile-home.png'),
                'sizes': '390x844',
                'type': 'image/png',
                'form_factor': 'narrow',
                'label': 'صفحه اصلی وینجاب در موبایل',
            },
            {
                'src': static('pwa/screenshots/mobile-dashboard.png'),
                'sizes': '390x844',
                'type': 'image/png',
                'form_factor': 'narrow',
                'label': 'داشبورد مدیریت وینجاب در موبایل',
            },
        ],
        'icons': [
            {'src': static(f'pwa/icons/icon-{size}.png'), 'sizes': f'{size}x{size}',
             'type': 'image/png', 'purpose': 'any'} for size in (192, 512)
        ] + [{'src': static('pwa/icons/maskable-512.png'), 'sizes': '512x512',
              'type': 'image/png', 'purpose': 'maskable'}],
    }, content_type='application/manifest+json', json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'public, max-age=0, must-revalidate'
    return response


@never_cache
@require_safe
def service_worker(request):
    # No request context processors: these bytes must never contain personal data.
    offline_html = render_to_string('pwa/offline.html')
    context = {'offline_url': reverse('pwa_offline')}
    source = render_to_string('pwa/service-worker.js', context)
    version = hashlib.sha256((source + offline_html).encode()).hexdigest()[:16]
    source = source.replace('__PWA_VERSION__', version)
    response = HttpResponse(source, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@require_safe
def offline(request):
    response = HttpResponse(render_to_string('pwa/offline.html'))
    response['X-Robots-Tag'] = 'noindex'
    return response
