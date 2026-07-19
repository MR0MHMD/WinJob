from django.urls import path
from .views import *

app_name = 'content_team'

urlpatterns = [
    # ==================== Team ====================
    path('', team_list_view, name='team_list'),
    path('team/<slug:slug>/', team_detail_view, name='team_detail'),
    path('plan/<int:plan_id>/', plan_detail, name='plan_detail'),

    # ==================== Dashboard ====================
    path('dashboard/', content_team_dashboard, name='dashboard'),
    path('dashboard/performance', team_performance_report, name='performance'),
    path('plans/management/', plans_dashboard, name='plans_dashboard'),

    # ==================== Order ====================
    path('team/orders/', team_orders_list, name='team_orders_list'),
    path('team/orders/<int:order_id>/', team_order_detail, name='team_order_detail'),
    path('team/orders/<int:order_id>/accept/', accept_order, name='accept_order'),
    path('team/orders/<int:order_id>/reject/', reject_order, name='reject_order'),
    path('team/orders/<int:order_id>/deliver/', deliver_order, name='deliver_order'),
    path('team/orders/<int:order_id>/revision/<int:revision_id>/accept/', accept_revision, name='accept_revision'),
    path('team/orders/<int:order_id>/revision/<int:revision_id>/reject/', reject_revision, name='reject_revision'),

    # ==================== Member ====================
    path('team/manage/', team_manage_view, name='team_manage'),
    path('team/<slug:team_slug>/members/manage/', team_members_manage, name='team_members_manage'),
    path('team/<slug:team_slug>/members/<int:member_id>/edit/', team_member_edit, name='team_member_edit'),
    path('team/<slug:team_slug>/requests/<int:request_id>/handle/', team_join_request_handle, name='team_join_request_handle'),

    # ==================== Coupon ====================
    path('team/coupons/', team_coupons, name='team_coupons'),
    path('team/coupons/create/', team_coupon_create, name='team_coupon_create'),
    path('team/coupons/<int:coupon_id>/edit/', team_coupon_edit, name='team_coupon_edit'),
    path('team/coupons/<int:coupon_id>/delete/', team_coupon_delete, name='team_coupon_delete'),

    # ==================== Plan ====================
    path('plans/management/<slug:service_slug>/', service_plans_management, name='service_plans'),
    path('plans/api/create/<slug:service_slug>/', create_plan, name='create_plan'),
    path('plans/api/edit/<int:plan_id>/', edit_plan, name='edit_plan'),
    path('plans/api/delete/<int:plan_id>/', delete_plan, name='delete_plan'),

    # ==================== Api ====================
    path('team/check-slug/', check_slug_availability, name='check_slug_availability'),
    path('submit-review/', submit_team_review_ajax, name='submit_review'),
    path('edit-review/', edit_team_review_ajax, name='edit_review'),
]
