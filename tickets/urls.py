from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # لیست تیکت‌ها
    path('', views.TicketListView.as_view(), name='ticket_list'),
    path('<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),

    # ایجاد تیکت جدید
    path('create/', views.TicketCreateView.as_view(), name='ticket_create'),

    # API برای گرفتن عنوان‌ها
    path('api/titles/<int:category_id>/', views.TicketTitleAPIView.as_view(), name='api_titles'),
]