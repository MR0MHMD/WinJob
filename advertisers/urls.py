from django.urls import path
from .views import *

app_name = 'advertisers'

urlpatterns = [
    # ==================== Dashboard ====================
    path('dashboard/', advertiser_dashboard, name='dashboard'),

    # ==================== List ====================
    path('campaign_list', campaigns_list, name='campaigns_list'),
    path('content_orders/', content_orders_list, name='content_orders_list'),

    # ==================== Detail ====================
    path('campaign_detail/<int:campaign_id>', campaign_detail, name='campaign_detail'),
    path('content_orders/<int:order_id>/', content_order_detail, name='content_order_detail'),

    # ==================== Api ====================
    path('campaign/select-option/', select_multi_choice_option, name='select_multi_choice_option'),
    path('campaign/order/<int:order_id>/request-revision/',  request_revision, name='request_revision'),
    path('campaign/order/<int:order_id>/final-accept/', final_accept_order, name='final_accept_order'),
    path('orders/<int:order_id>/delete/', delete_content_order, name='delete_content_order'),
]
