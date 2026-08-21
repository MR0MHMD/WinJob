from django.urls import path
from .views import *

app_name = 'payment'

urlpatterns = [
    # Wallet
    path('wallet/', wallet_dashboard, name='wallet_dashboard'),
    path('wallet/deposit/', wallet.wallet_deposit, name='wallet_deposit'),
    path('wallet/callback/', wallet.payment_callback, name='payment_callback'),
    path('wallet/transactions/load-more/', load_more_transactions, name='load_more_transactions'),

    # Invoice
    path('invoices/', invoice_list, name='invoice_list'),
    path('invoices/detail/<int:invoice_id>/', invoice_detail, name='invoice_detail'),
    path('invoices/<int:invoice_id>/print/', invoice_print, name='invoice_print'),
    path('invoices/<int:invoice_id>/cancel/', cancel_invoice, name='cancel_invoice'),
    path('invoices/<int:invoice_id>/pay/', redirect_to_payment, name='redirect_to_payment'),
    path('campaign/callback/', campaign_payment_callback, name='campaign_payment_callback'),
]