from django.urls import path
from .api_views import *
from .views import *

app_name = 'accounts'

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('edit/', advertiser_profile_edit_view, name='edit'),
    path('update/', user_update, name='update'),
    path('delete_account/', delete_account, name='delete_account'),
    path('wallet/', wallet_dashboard, name='wallet_dashboard'),
    path('wallet/deposit/', wallet_deposit, name='wallet_deposit'),
    path('wallet/transactions/load-more/', load_more_transactions, name='load_more_transactions'),
    path('dashboard/router/', dashboard_router, name='dashboard_router'),
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('api/send-otp/', send_otp_api, name='send_otp_api'),
    path('api/verify-otp/', verify_otp_api, name='verify_otp_api'),
    path('api/resend-otp/', resend_otp_api, name='resend_otp_api'),
    path('api/get-otp-status/', get_otp_status_api, name='get_otp_status_api'),
    path('api/complete-registration/', complete_registration_api, name='complete_registration_api'),
    path('api/resend-login-otp/', resend_login_otp_api, name='resend_login_otp_api'),
    path('api/verify-login-otp/', verify_login_otp_api, name='verify_login_otp_api'),
    path('api/set-login-phone/', set_login_phone_api, name='set_login_phone_api'),
    path('api/check-user/', check_user_exists_api, name='check_user_exists'),
    path('api/login-otp-request/', login_otp_request_api, name='login_otp_request_api'),
    ]
