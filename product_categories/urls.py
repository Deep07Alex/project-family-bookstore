from django.urls import path 
from . import views

urlpatterns = [
   path('', views.productcatagory, name="productcatagory"),
   path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]