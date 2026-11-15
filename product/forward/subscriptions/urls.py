"""مسیرهای URL اپ اشتراک وین فوروارد."""

from django.urls import path

from . import views

app_name = "forward_subscriptions"

urlpatterns = [
    path("", views.plans_view, name="plans"),
    path("order/create/", views.create_order_view, name="create_order"),
    path("order/<int:order_id>/", views.order_detail_view, name="order_detail"),
    path("order/<int:order_id>/pay-wallet/", views.pay_wallet_view, name="pay_wallet"),
    path("order/<int:order_id>/pay-gateway/", views.pay_gateway_view, name="pay_gateway"),
]
