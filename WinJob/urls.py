from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from core import pwa

handler404 = 'core.views.errors.custom_404'
handler502 = 'core.views.errors.custom_502'
handler500 = 'core.views.errors.custom_500'
handler403 = 'core.views.errors.custom_403'
handler401 = 'core.views.errors.custom_401'
handler429 = 'core.views.errors.custom_429'
handler503 = 'core.views.errors.custom_503'

urlpatterns = [
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('service-worker.js', pwa.service_worker, name='pwa_service_worker'),
    path('offline/', pwa.offline, name='pwa_offline'),
    path('admin/', admin.site.urls),
    path('accounts/', include("accounts.urls", namespace="accounts")),
    path('notifications/', include("notifications.urls", namespace="notifications")),
    path('advertisers/', include("advertisers.urls", namespace="advertisers")),
    path('influencers/', include("influencers.urls", namespace="influencers")),
    path('content_team/', include("content_team.urls", namespace="content_team")),
    path('campaigns/', include("campaigns.urls", namespace="campaigns")),
    path('tickets/', include("tickets.urls", namespace="tickets")),
    path('blog/', include("blog.urls", namespace="blog")),
    path('gamification/', include("gamification.urls", namespace="gamification")),
    path('support/', include("support.urls", namespace="support")),
    path('payment/', include("payment.urls", namespace="payment")),
    path('gateway/', include("django_iranian_payment.contrib.django.urls")),
    path('', include("core.urls", namespace="core")),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
