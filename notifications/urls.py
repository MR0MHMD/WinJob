from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('update-preferences/', views.update_preferences, name='update_preferences'),
    path('mark-read/<int:notif_id>/', views.mark_notification_read, name='mark_read'),
]