from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView, UserProfileView, ItemListingViewSet, 
    ReviewViewSet, search_marketplace
)

router = DefaultRouter()
router.register(r'items', ItemListingViewSet, basename='item')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = [
    # Аутентификация и Профиль
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    
    # Поиск по нескольким сущностям
    path('search/', search_marketplace, name='search'),
    
    # РоутыViewSet (Объявления, Отзывы)
    path('', include(router.urls)),
]