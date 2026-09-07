from django.urls import path
from .views import *

app_name = 'core'

urlpatterns = [
    path('', home, name='home'),
    path("about/", AboutView.as_view(), name="about"),
    path('landing/<slug:slug>/', platform_landing_page, name='landing_page'),
    path('pending', pending, name='pending'),
    path("terms/", TermsView.as_view(), name="terms"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("help/", HelpGuideView.as_view(), name="help"),
    path("guide/", HelpGuideView.as_view(), name="guide"),
    path("faq/", FAQPageView.as_view(), name="faq"),
    path("faq/", FAQPageView.as_view(), name="faq"),
    path("faq/api/titles/<int:category_id>/", faq_titles_api, name="faq_titles_api"),
    path("faq/api/questions/<int:title_id>/", faq_questions_api, name="faq_questions_api"),
    path("404/", custom_404, name="404"),
    path("502/", custom_502, name="502"),
    path("500/", custom_500, name="500"),
    path("403/", custom_403, name="403"),
    path("401/", custom_401, name="401"),
    path("429/", custom_429, name="429"),
    path("503/", custom_503, name="503"),
]
