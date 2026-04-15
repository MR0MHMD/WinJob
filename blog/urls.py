from django.urls import path
from .views import *

app_name = 'blog'

urlpatterns = [
    path('list/', post_list, name='list'),
    path('detail/<int:id>/<slug:slug>', post_detail, name='detail'),
    path('comment/<int:id>/<slug:slug>/<int:parent_id>', post_comment, name='comment'),
    path('person_posts/<int:id>', person_posts, name='person_posts'),
]
