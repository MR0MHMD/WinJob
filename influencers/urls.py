from django.urls import path
from . import api_views
from . import views

app_name = 'influencers'

urlpatterns = [
    path('dashboard/', views.influencer_dashboard, name='dashboard'),
    path('update/', api_views.profile_update, name='update'),
    path('my_channels/', views.influencer_channels_view, name='influencer_channels'),
    path('my_channels/edit/<int:pk>/', views.influencer_channels_view, name='edit_channel'),
    path('my_channels/delete/<int:pk>/', views.delete_channel_view, name='delete_channel'),
    path('service-rates/', views.service_rates_view, name='service_rates'),
    path('service-rates/edit/<int:channel_id>/<int:ad_type_id>/', api_views.rate_inline_edit, name='rate_inline_edit'),
    path('order_list/', views.order_list.as_view(), name="order_list"),
    path('order_detail/<int:order_id>', views.order_detail, name="order_detail"),
    path('order_detail/<int:order_id>/response', views.influencer_respond, name="influencer_respond"),
    path('order_detail/<int:order_id>/report/', views.submit_report, name='submit_report'),
    path('channels/', views.channel_list, name='channel_list'),
    path('channels/<int:channel_id>/', views.channel_detail, name='channel_detail'),
]
