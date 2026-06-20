from django.urls import path
from . import views
from .api_views import get_provinces_data

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path("about/", views.AboutView.as_view(), name="about"),
    path('api/provinces/', get_provinces_data, name='get_provinces'),
    path('landing/<slug:slug>/', views.platform_landing_page, name='landing_page'),
    path('pending', views.pending, name='pending'),
]
