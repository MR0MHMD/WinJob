from django.urls import path
from support.views import list, detail, dashboard, api

app_name = 'support'

urlpatterns = [
    # ==================== داشبورد ها ====================
    path('finance/', dashboard.FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('', dashboard.DashboardView.as_view(), name='dashboard'),

    # ==================== لیست ها ====================
    path('content-orders/', list.ContentOrderListView.as_view(), name='content_order_list'),
    path('notifications/', list.NotificationListView.as_view(), name='notification_list'),
    path('bookings/', list.CampaignBookingListView.as_view(), name='booking_list'),
    path('campaigns/', list.CampaignListView.as_view(), name='campaign_list'),
    path('channels/', list.ChannelListView.as_view(), name='channel_list'),
    path('tickets/', list.TicketListView.as_view(), name='ticket_list'),
    path('reports/', list.ReportListView.as_view(), name='report_list'),
    path('users/', list.UserListView.as_view(), name='user_list'),
    path('teams/', list.TeamListView.as_view(), name='team_list'),

    # ==================== جزئیات ها ====================
    path('content-orders/<int:pk>/', detail.ContentOrderDetailView.as_view(), name='content_order_detail'),
    path('campaigns/<int:pk>/', detail.CampaignDetailView.as_view(), name='campaign_detail'),
    path('channels/<int:pk>/', detail.ChannelDetailView.as_view(), name='channel_detail'),
    path('reports/<int:pk>/', detail.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<int:pk>/', detail.ReportDetailView.as_view(), name='report_detail'),
    path('tickets/<int:pk>/', detail.TicketDetailView.as_view(), name='ticket_detail'),
    path('users/<int:pk>/', detail.UserDetailView.as_view(), name='user_detail'),
    path('teams/<int:pk>/', detail.TeamDetailView.as_view(), name='team_detail'),

    # ==================== اکشن ها ====================
    path('campaigns/<int:pk>/approve/', api.CampaignApproveView.as_view(), name='campaign_approve'),
    path('campaigns/<int:pk>/reject/', api.CampaignRejectView.as_view(), name='campaign_reject'),
    path('channels/<int:pk>/approve/', api.ChannelApproveView.as_view(), name='channel_approve'),
    path('reports/<int:pk>/approve/', api.ReportApproveView.as_view(), name='report_approve'),
    path('channels/<int:pk>/reject/', api.ChannelRejectView.as_view(), name='channel_reject'),
    path('reports/<int:pk>/reject/', api.ReportRejectView.as_view(), name='report_reject'),
    path('tickets/<int:pk>/reply/', api.TicketReplyView.as_view(), name='ticket_reply'),
]
