# market/urls.py

from django.urls import path
from .views import *
from .minipay_views import *
from .api_views import *

app_name = "market"

urlpatterns = [
    path("", MarketLandingView.as_view(), name="landing"),
    path("product/<slug:slug>/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
    # Cart
    path("cart/", CartDetailView.as_view(), name="cart_detail"),
    path("cart/mini/", MiniCartView.as_view(), name="mini_cart"),
    path("cart/add/<int:pk>/", CartAddView.as_view(), name="cart_add"),
    path("cart/update/<int:item_id>/", CartUpdateView.as_view(), name="cart_update"),
    path("cart/remove/<int:item_id>/", CartRemoveView.as_view(), name="cart_remove"),
    path("cart/clear/", CartClearView.as_view(), name="cart_clear"),
    path("checkout/start/", StartCheckoutView.as_view(), name="checkout_start"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("checkout/confirm/", CheckoutConfirmView.as_view(), name="checkout_confirm"),
    path("checkout/change-address/", ChangeAddressView.as_view(), name="change_address"),
    path("checkout/callback/", market_order_payment_callback, name="market_order_payment_callback"),

    # Address AJAX
    path("checkout/address/save/", SaveAddressView.as_view(), name="address_save"),
    path("checkout/address/update/<int:address_id>/", UpdateAddressView.as_view(), name="address_update"),
    path("checkout/address/delete/<int:address_id>/", DeleteAddressView.as_view(), name="address_delete"),
    path("checkout/address/use/<int:address_id>/", UseAddressView.as_view(), name="address_use"),

    # API
    path("api/cities/", CitiesByProvinceView.as_view(), name="cities_by_province"),
    path("api/address/<int:address_id>/", AddressDetailAPIView.as_view(), name="address_detail_api"),

    # Orders
    path("orders/", OrderListView.as_view(), name="order_list"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/confirm-delivery/", ConfirmDeliveryView.as_view(), name="order_confirm_delivery"),

    # ============ Seller Panel ============
    path("seller/dashboard", SellerDashboardView.as_view(), name="seller_dashboard"),
    path("seller/products/", SellerProductListView.as_view(), name="seller_product_list"),
    path("seller/products/create/", SellerProductCreateView.as_view(), name="seller_product_create"),
    path("seller/products/<int:pk>/edit/", SellerProductUpdateView.as_view(), name="seller_product_update"),
    path("seller/products/<int:pk>/delete/", SellerProductDeleteView.as_view(), name="seller_product_delete"),
    path("seller/products/images/<int:pk>/delete/", SellerProductImageDeleteView.as_view(),
         name="seller_product_image_delete"),
    path("seller/products/<int:pk>/set-main-image/", SellerSetMainImageAPIView.as_view(), name="seller_set_main_image"),

    # API
    path("api/translate-slug/", TranslateSlugAPIView.as_view(), name="translate_slug"),

    path('checkout/<int:product_id>/', GuestCheckoutView.as_view(), name='guest_checkout'),
    path('pay/<int:order_id>/initiate/', GuestPaymentInitiateView.as_view(), name='guest_pay_initiate'),
    path('pay/<int:order_id>/verify/', GuestPaymentVerifyView.as_view(), name='guest_pay_verify'),
    path('pay/<int:order_id>/result/', GuestPaymentResultView.as_view(), name='guest_pay_result'),

    path('support-order/request/', support_order_request, name='support_order_request'),

    path('api/bot/product/active/', bot_active_product_api, name='bot_active_product_api'),
]
