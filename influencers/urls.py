from django.urls import path
from . import api_views
from . import views

app_name = 'influencers'

urlpatterns = [
    path('dashboard/', views.influencer_dashboard, name='dashboard'),
    path('my_channels/', views.influencer_channels_view, name='influencer_channels'),
    path('my_channels/edit/<int:pk>/', views.influencer_channels_view, name='edit_channel'),
    path('my_channels/delete/<int:pk>/', views.delete_channel_view, name='delete_channel'),
    path('service-rates/', views.service_rates_view, name='service_rates'),
    path('service-rates/edit/<int:channel_id>/<int:ad_type_id>/', api_views.rate_inline_edit, name='rate_inline_edit'),
    path('order_list/', views.order_list, name="order_list"),
    path('order_detail/<int:order_id>', views.order_detail, name="order_detail"),
    path('order_detail/<int:order_id>/response', views.influencer_respond, name="influencer_respond"),
    path('order_detail/<int:order_id>/report/', views.submit_report, name='submit_report'),
    path('channels/', views.channel_list, name='channel_list'),
    path('channels/<int:channel_id>/', views.channel_detail, name='channel_detail'),
    path('coupons/', views.influencer_coupons, name='coupon_list'),
    path('coupons/create/', views.coupon_create, name='coupon_create'),
    path('coupons/<int:coupon_id>/edit/', views.coupon_edit, name='coupon_edit'),
    path('coupons/<int:coupon_id>/delete/', views.coupon_delete, name='coupon_delete'),
    path('submit-review/', api_views.submit_influencer_review_ajax, name='submit_review'),
    path('edit-review/', api_views.edit_influencer_review_ajax, name='edit_review'),
    path('channel/<int:channel_id>/verify-modal/', api_views.verify_channel_modal, name='verify_channel_modal'),
    path('channel/<int:channel_id>/start-verify/', api_views.start_verification, name='start_verification'),
    path('channel/<int:channel_id>/callback/', api_views.verification_callback, name='verification_callback'),
    path('channel/<int:channel_id>/verification-status/', api_views.verification_status, name='verification_status'),
    path('report/<int:report_id>/n8n-callback/', api_views.n8n_report_callback, name='n8n_report_callback'),
]
