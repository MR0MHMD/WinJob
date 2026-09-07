from payment.views.bank_acount import bank_account_list, detect_bank_api,bank_account_create_modal, bank_account_delete, bank_account_set_default
from payment.views.invoice import invoice_list, invoice_detail, invoice_print, cancel_invoice, redirect_to_payment, campaign_payment_callback
from payment.views.withdrawal import withdrawal_list, withdrawal_detail, withdrawal_create, withdrawal_cancel
from payment.views.wallet import wallet_dashboard, load_more_transactions, wallet_deposit
