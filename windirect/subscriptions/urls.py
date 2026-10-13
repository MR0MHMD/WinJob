from django.urls import path
from . import views

urlpatterns = [
    path("plans/", views.plans, name="plans"),
    path("plans/<int:pk>/trial/", views.trial, name="trial_activate"),

    # شروع خرید از یک پلن (بدون order_pk)
    path("plans/<int:offer_pk>/checkout/", views.checkout, name="checkout_offer"),

    # صفحهٔ پرداخت یک سفارش مشخص
    path("subscription/orders/<int:order_pk>/checkout/", views.checkout, name="subscription_checkout"),

    path("subscription/", views.subscription, name="subscription"),
    path("subscription/orders/<int:pk>/", views.order_detail, name="subscription_order"),
    path("subscription/orders/<int:pk>/cancel/", views.cancel_order, name="subscription_cancel"),
    path("subscription/orders/<int:pk>/apply-coupon/", views.apply_coupon, name="apply_subscription_coupon"),
    path("subscription/orders/<int:pk>/remove-coupon/", views.remove_coupon, name="remove_subscription_coupon"),
]