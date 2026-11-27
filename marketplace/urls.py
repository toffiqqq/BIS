from django.urls import path
from . import views

urlpatterns = [
    path('', views.item_list, name='item_list'),             # главная: баннер + каталог
    path('add/', views.add_item, name='add_item'),
    path('items/<int:item_id>/', views.item_detail, name='item_detail'),
    path('items/<int:item_id>/sold/', views.mark_as_sold, name='mark_as_sold'),
    path('items/<int:item_id>/buy/', views.buy_item, name='buy_item'),
    path('profile/', views.profile, name='profile'),
    path('wallet/<str:kind>/', views.wallet_operation, name='wallet'),  # deposit | withdraw
    path('sellers/<str:username>/reviews/', views.seller_reviews, name='seller_reviews'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('login/code/', views.verify_phone, name='verify_phone'),
    path('logout/', views.logout_view, name='logout'),
]
