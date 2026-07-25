from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path("about/", views.AboutView.as_view(), name="about"),
    path('landing/<slug:slug>/', views.platform_landing_page, name='landing_page'),
    path('pending', views.pending, name='pending'),
]
