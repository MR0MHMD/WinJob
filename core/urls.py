from django.urls import path
from .views import home, landing_page
from .api_views import get_provinces_data

app_name = 'core'

urlpatterns = [
    path('', home, name='home'),
    path('api/provinces/', get_provinces_data, name='get_provinces'),
    path('landing/<slug:platform>/', landing_page, name='landing_page'),
]
