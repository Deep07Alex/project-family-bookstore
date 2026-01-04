from django.urls import path 
from . import views

urlpatterns = [
   path('', views.productcatagory, name="productcatagory"),
   path('<str:category_type>/', views.product_category_detail, name="product_category_detail"),
   path('<str:category_type>/load-more/', views.product_category_load_more, name='product_category_load_more'),
   path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]