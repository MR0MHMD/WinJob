from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include("accounts.urls", namespace="accounts")),
    path('notifications/', include("notifications.urls", namespace="notifications")),
    path('advertisers/', include("advertisers.urls", namespace="advertisers")),
    path('influencers/', include("influencers.urls", namespace="influencers")),
    path('content_team/', include("content_team.urls", namespace="content_team")),
    path('campaigns/', include("campaigns.urls", namespace="campaigns")),
    path('tickets/', include("tickets.urls", namespace="tickets")),
    path('blog/', include("blog.urls", namespace="blog")),
    path('', include("core.urls", namespace="core")),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)