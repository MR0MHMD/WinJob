from django.urls import path
from .views import api_views, auth_views, views, auth_api_views

app_name = 'accounts'

urlpatterns = [
    # auth_views
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    path('verify-otp/', auth_views.verify_otp_view, name='verify_otp'),

    # view
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('wallet/', views.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/deposit/', views.wallet_deposit, name='wallet_deposit'),
    path('wallet/transactions/load-more/', views.load_more_transactions, name='load_more_transactions'),

    # api_views
    path('delete_account/', api_views.delete_account, name='delete_account'),
    path('dashboard/router/', api_views.dashboard_router, name='dashboard_router'),

    # auth_api_views
    path('api/request-otp/', auth_api_views.request_otp_api, name='request_otp_api'),
    path('api/check-phone/', auth_api_views.check_phone_api, name='check_phone_api'),
    path('api/verify-otp/', auth_api_views.verify_otp_api, name='verify_otp_api'),
    path('api/resend-otp/', auth_api_views.resend_otp_api, name='resend_otp_api'),
]
