from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    path('points-guide/', views.points_guide, name='points_guide'),
    path('points-guide/channel/<int:channel_id>/', views.points_guide, name='points_guide_channel'),
]