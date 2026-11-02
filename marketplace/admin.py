from django.contrib import admin
from .models import User, Category, ItemListing, Transaction, Review

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'student_id', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')
    search_fields = ('username', 'email', 'student_id')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)

@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'status', 'seller', 'category', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'seller__username')
    list_editable = ('status', 'price')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'buyer', 'completed_at')
    readonly_fields = ('completed_at',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'reviewer', 'seller', 'rating', 'created_at')
    list_filter = ('rating',)