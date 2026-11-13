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

class TransactionInline(admin.StackedInline):
    """Транзакция (покупатель) прямо на странице объявления — только просмотр."""
    model = Transaction
    fields = ('buyer', 'completed_at')
    readonly_fields = ('buyer', 'completed_at')
    can_delete = False
    extra = 0
    max_num = 0


@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'status', 'seller', 'buyer', 'category', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'seller__username', 'transaction__buyer__username')
    list_editable = ('status', 'price')
    list_select_related = ('seller', 'category', 'transaction__buyer')
    inlines = [TransactionInline]

    @admin.display(description='Buyer', ordering='transaction__buyer__username')
    def buyer(self, obj):
        tx = getattr(obj, 'transaction', None)
        return tx.buyer if tx else '—'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'seller', 'buyer', 'listing_price', 'completed_at')
    list_select_related = ('listing__seller', 'buyer')
    search_fields = ('listing__title', 'listing__seller__username', 'buyer__username')
    readonly_fields = ('completed_at',)
    raw_id_fields = ('listing', 'buyer')

    @admin.display(description='Seller', ordering='listing__seller__username')
    def seller(self, obj):
        return obj.listing.seller

    @admin.display(description='Price', ordering='listing__price')
    def listing_price(self, obj):
        return obj.listing.price

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'reviewer', 'seller', 'rating', 'created_at')
    list_filter = ('rating',)