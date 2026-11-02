from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from django.db.models import Q

from .models import User, Category, ItemListing, Transaction, Review
from .serializers import (
    RegisterSerializer, UserProfileSerializer, CategorySerializer,
    ItemListingSerializer, ReviewSerializer
)


class IsAdminUserRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.role == 'Admin' or request.user.is_staff)



class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user



class ItemListingViewSet(viewsets.ModelViewSet):
    queryset = ItemListing.objects.all().order_by('-created_at')
    serializer_class = ItemListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def mark_as_sold(self, request, pk=None):
        item = self.get_object()
        
        if item.seller != request.user and request.user.role != 'Admin':
            return Response({"error": "У вас нет прав для изменения статуса этого товара."}, status=status.HTTP_403_FORBIDDEN)
        
        item.status = 'Sold'
        item.save()
        
        Transaction.objects.create(listing=item, buyer=request.user)
        
        return Response({"status": "Товар успешно отмечен как Sold", "item_id": item.id})



class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all().order_by('-created_at')
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)



@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def search_marketplace(request):
    query = request.query_params.get('q', '')
    min_price = request.query_params.get('min_price')
    max_price = request.query_params.get('max_price')

    items = ItemListing.objects.filter(status='Active')

    if query:
        items = items.filter(
            Q(title__icontains=query) |
            Q(seller__username__icontains=query) |
            Q(category__name__icontains=query)
        )

    if max_price:
        items = items.filter(price__lte=max_price)
    if min_price:
        items = items.filter(price__gte=min_price)

    serializer = ItemListingSerializer(items, many=True)
    return Response({
        "count": items.count(),
        "query": query,
        "results": serializer.data
    })