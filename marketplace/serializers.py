from rest_framework import serializers
from .models import User, Category, ItemListing, Transaction, Review

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'student_id', 'role')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            student_id=validated_data.get('student_id', ''),
            role=validated_data.get('role', 'Student')
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'student_id', 'role', 'date_joined')
        read_only_fields = ('id', 'role', 'date_joined')


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ItemListingSerializer(serializers.ModelSerializer):
    seller_username = serializers.ReadOnlyField(source='seller.username')
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = ItemListing
        fields = ('id', 'title', 'price', 'status', 'created_at', 'seller', 'seller_username', 'category', 'category_name')
        read_only_fields = ('seller', 'status', 'created_at')

   
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена товара должна быть больше 0 KZT.")
        if value > 100000:
            raise serializers.ValidationError("Превышен максимальный лимит стоимости товара (100,000 KZT).")
        return value

   
    def validate(self, attrs):
        user = self.context['request'].user
        active_ads_count = ItemListing.objects.filter(seller=user, status='Active').count()
        
        
        if not self.instance and active_ads_count >= 10:
            raise serializers.ValidationError("Превышен лимит: студент не может иметь более 10 активных объявлений одновременно.")
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.ReadOnlyField(source='reviewer.username')

    class Meta:
        model = Review
        fields = ('id', 'rating', 'comment', 'created_at', 'reviewer', 'reviewer_username', 'seller', 'listing')
        read_only_fields = ('reviewer', 'created_at')