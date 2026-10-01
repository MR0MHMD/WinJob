from django.urls import path

from . import views

app_name = "windirect"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/", views.connections, name="connections"),
    path("rules/", views.rules, name="rules"),
    path("rules/new/", views.rule_create, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    path("rules/<int:pk>/toggle/", views.rule_toggle, name="rule_toggle"),
    path("rules/<int:pk>/delete/", views.rule_delete, name="rule_delete"),
    path("test/", views.simulation, name="simulation"),
    path("logs/", views.logs, name="logs"),
]

from . import features_views

urlpatterns += [
    path('tools/<str:kind>/', features_views.asset_list, name='asset_list'),
    path('tools/<str:kind>/new/', features_views.asset_edit, name='asset_create'),
    path('tools/<str:kind>/<int:pk>/edit/', features_views.asset_edit, name='asset_edit'),
    path('tools/<str:kind>/<int:pk>/toggle/', features_views.asset_toggle, name='asset_toggle'),
    path('tools/<str:kind>/<int:pk>/delete/', features_views.asset_delete, name='asset_delete'),
    path('direct/test/', features_views.direct_simulation, name='direct_simulation'),
    path('direct/logs/', features_views.direct_logs, name='direct_logs'),
    path('forms/<int:pk>/responses/', features_views.submissions, name='submissions'),
    path('forms/<int:pk>/export/', features_views.export_submissions, name='export_submissions'),
    path('responses/<int:pk>/', features_views.submission_detail, name='submission_detail'),
]

from .subscriptions import views as subscription_views

urlpatterns += [
    path('plans/', subscription_views.plans, name='plans'),
    path('plans/<int:pk>/trial/', subscription_views.trial, name='trial_activate'),
    path('plans/<int:pk>/buy/', subscription_views.subscribe, name='subscribe'),
    path('subscription/', subscription_views.subscription, name='subscription'),
    path('subscription/orders/<int:pk>/checkout/', subscription_views.checkout, name='subscription_checkout'),
    path('subscription/orders/<int:pk>/', subscription_views.order_detail, name='subscription_order'),
    path('subscription/orders/<int:pk>/cancel/', subscription_views.cancel_order, name='subscription_cancel'),
    path('accounts/<int:pk>/toggle/', subscription_views.connection_toggle, name='connection_toggle'),
]
