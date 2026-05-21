from django.urls import path
from .views import plan_views, api_views, views

app_name = 'content_team'

urlpatterns = [
    path('dashboard/', views.content_team_dashboard, name='dashboard'),
    path('', views.team_list_view, name='team_list'),
    path('<slug:slug>/', views.team_detail_view, name='team_detail'),
    path('team/manage/', views.team_manage_view, name='team_manage'),
    path('team/check-slug/', api_views.check_slug_availability, name='check_slug_availability'),
    path('team/<slug:team_slug>/members/manage/', views.team_members_manage, name='team_members_manage'),
    path('team/<slug:team_slug>/members/<int:member_id>/edit/', api_views.team_member_edit, name='team_member_edit'),
    path('team/<slug:team_slug>/requests/<int:request_id>/handle/', api_views.team_join_request_handle, name='team_join_request_handle'),
    path('team/orders/', views.team_orders_list, name='team_orders_list'),
    path('team/orders/<int:order_id>/', views.team_order_detail, name='team_order_detail'),
    path('team/orders/<int:order_id>/accept/', views.accept_order, name='accept_order'),
    path('team/orders/<int:order_id>/reject/', views.reject_order, name='reject_order'),
    path('team/orders/<int:order_id>/deliver/', views.deliver_order, name='deliver_order'),
    path('team/orders/<int:order_id>/revision/<int:revision_id>/accept/', views.accept_revision, name='accept_revision'),
    path('team/orders/<int:order_id>/revision/<int:revision_id>/reject/', views.reject_revision, name='reject_revision'),
    path('team/coupons/', views.team_coupons, name='team_coupons'),
    path('team/coupons/create/', views.team_coupon_create, name='team_coupon_create'),
    path('team/coupons/<int:coupon_id>/edit/', views.team_coupon_edit, name='team_coupon_edit'),
    path('team/coupons/<int:coupon_id>/delete/', views.team_coupon_delete, name='team_coupon_delete'),
    path('plan/<int:plan_id>/', plan_views.plan_detail, name='plan_detail'),
    path('plans/management/', plan_views.plans_dashboard, name='plans_dashboard'),
    path('plans/management/<slug:service_slug>/', plan_views.service_plans_management, name='service_plans'),
    path('plans/api/create/<slug:service_slug>/', plan_views.create_plan, name='create_plan'),
    path('plans/api/edit/<int:plan_id>/', plan_views.edit_plan, name='edit_plan'),
    path('plans/api/delete/<int:plan_id>/', plan_views.delete_plan, name='delete_plan'),
]
