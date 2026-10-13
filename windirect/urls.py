"""تجمیع مسیرهای اپ‌ها با حفظ نام‌ها و آدرس‌های فعلی پنل."""

from django.urls import path
from .views.dashboard import dashboard
from .connections.urls import urlpatterns as connection_urls
from .comments.urls import urlpatterns as comment_urls
from .direct.urls import urlpatterns as direct_urls
from .showcases.urls import urlpatterns as showcase_urls
from .forms.urls import urlpatterns as form_urls
from .subscriptions.urls import urlpatterns as subscription_urls

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
