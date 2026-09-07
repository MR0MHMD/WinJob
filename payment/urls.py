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

    path('withdrawals/', withdrawal_list, name='withdrawal_list'),
    path('withdrawals/create/', withdrawal_create, name='withdrawal_create'),
    path('withdrawals/<int:withdrawal_id>/', withdrawal_detail, name='withdrawal_detail'),
    path('withdrawals/<int:withdrawal_id>/cancel/', withdrawal_cancel, name='withdrawal_cancel'),

    path('bank-accounts/', bank_account_list, name='bank_account_list'),
    path('bank-accounts/create-modal/', bank_account_create_modal, name='bank_account_create_modal'),
    path('detect-bank/', detect_bank_api, name='detect_bank'),
    path('bank-accounts/<int:account_id>/delete/', bank_account_delete, name='bank_account_delete'),
    path('bank-accounts/<int:account_id>/set-default/', bank_account_set_default, name='bank_account_set_default'),
]