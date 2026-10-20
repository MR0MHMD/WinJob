"""تجمیع مسیرهای اپ‌ها با حفظ نام‌ها و آدرس‌های فعلی پنل."""

from django.urls import path
from windirect.common.dashboard import dashboard
from windirect.connections.urls import urlpatterns as connection_urls
from windirect.comments.urls import urlpatterns as comment_urls
from windirect.direct.urls import urlpatterns as direct_urls
from windirect.showcases.urls import urlpatterns as showcase_urls
from windirect.forms.urls import urlpatterns as form_urls
from windirect.subscriptions.urls import urlpatterns as subscription_urls

app_name = "windirect"

urlpatterns = [path("", dashboard, name="dashboard")]
urlpatterns += (
    connection_urls
    + comment_urls
    + direct_urls
    + showcase_urls
    + form_urls
    + subscription_urls
)