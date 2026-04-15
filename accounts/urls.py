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
]
