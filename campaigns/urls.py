from django.urls import path
from .views import *

app_name = 'campaigns'

urlpatterns = [
    # view
    path('campaign_create_step1', campaign_create_step1, name='campaign_create_step1'),
    path('campaign_edit/<int:campaign_id>/step1/', campaign_create_step1, name='campaign_edit_step1'),
    path('campaign_create_step2', campaign_create_step2, name='campaign_create_step2'),
    path("campaign_create_step3", campaign_create_step3_router, name="campaign_create_step3"),
    path("campaign_create_step3/ready", campaign_create_step3_ready, name="campaign_create_step3_ready"),
    path("campaign_create_step3/team", campaign_create_step3_team, name="campaign_create_step3_team"),
    path('campaign_create_step4', campaign_create_step4, name='campaign_create_step4'),

    # replacement
    path('select/replacement/<int:campaign_id>/', campaign_select_replacement, name='campaign_select_replacement'),
    path('replace-team/<int:campaign_id>/', campaign_replace_team, name='campaign_replace_team'),
    path('switch-to-ready/<int:campaign_id>/', campaign_switch_to_ready, name='campaign_switch_to_ready'),
    path('continue-without-replacement/<int:campaign_id>/', campaign_continue_without_replacement, name='campaign_continue_without_replacement'),
    path('switch-to-ready-cancel/<int:campaign_id>/', campaign_switch_to_ready_cancel, name='campaign_switch_to_ready_cancel'),

    # tracking
    path("r/<str:code>/", track_click, name="track_click"),

    # api
    path('api/calculate-influencer-commission/', calculate_influencer_replacement_commission, name='calculate_influencer_commission'),
    path("api/content-team-rates/", api_content_team_rates, name="api_content_team_rates"),
    path('delete/<int:campaign_id>/', campaign_delete, name='campaign_delete'),
    path('campaign_create_step2/calculate', campaign_step2_calculate_price, name='step2_calculate'),
    path('campaign_create_step4/apply_discount', apply_discount_code, name='apply_discount'),
]
