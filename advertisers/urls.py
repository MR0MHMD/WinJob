from django.urls import path
from .api_views import *
from .views import *

app_name = 'advertisers'

urlpatterns = [
    path('my_campaigns', campaigns_list, name='my_campaigns'),
    path('campaign_detail/<int:campaign_id>', campaign_detail, name='campaign_detail'),
    path('update/', profile_update, name='update'),
    path('dashboard/', advertiser_dashboard, name='dashboard'),
    path('campaign/order/<int:order_id>/request-revision/',  request_revision, name='request_revision'),
    path('campaign/order/<int:order_id>/final-accept/', final_accept_order, name='final_accept_order'),
]
