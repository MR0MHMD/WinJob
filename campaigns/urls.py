from django.urls import path
from .views import *
from .api_views import *

app_name = 'campaigns'

urlpatterns = [
    path('campaign_create_step1', campaign_create_step1, name='campaign_create_step1'),
    path('campaign_create_step2', campaign_create_step2, name='campaign_create_step2'),
    path("campaign_create_step3", campaign_create_step3_router, name="campaign_create_step3"),
    path("campaign_create_step3/ready", campaign_create_step3_ready, name="campaign_create_step3_ready"),
    path("api/content-team-rates/", api_content_team_rates, name="api_content_team_rates", ),
    path("campaign_create_step3/team", campaign_create_step3_team, name="campaign_create_step3_team"),
    path('campaign_create_step4', campaign_create_step4, name='campaign_create_step4'),
    path('campaign_create_step2/calculate', campaign_step2_calculate_price, name='step2_calculate'),
    path('campaign_create_step4/apply_discount', apply_discount_code, name='apply_discount'),
    path("r/<str:code>/", track_click, name="track_click"),
]
