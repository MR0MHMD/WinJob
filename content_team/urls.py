from django.urls import path
from . import views
from . import api_views

app_name = 'content_team'

urlpatterns = [
    path('dashboard/', views.content_team_dashboard, name='dashboard'),
    path('', views.team_list_view, name='team_list'),
    path('<slug:slug>/', views.team_detail_view, name='team_detail'),
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
]
