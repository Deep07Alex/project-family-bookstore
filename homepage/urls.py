from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_page, name='home_page'),
    path('books/<slug:slug>/', views.book_detail, name='book_detail'),
    path('category/<str:category_slug>/', views.category_view, name='category_view'),
    path('category/<str:category_slug>/load-more/', views.category_load_more, name='category_load_more'),
]