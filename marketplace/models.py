from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, default='Student') 

    def __str__(self):
        return self.username


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ItemListing(models.Model):
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='Active') 
    created_at = models.DateTimeField(auto_now_add=True)
    
    seller = models.ForeignKey(
        User, 
        on_delete=models.RESTRICT, 
        related_name='listings'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.RESTRICT,
        related_name='items'
    )

    def __str__(self):
        return self.title


class Transaction(models.Model):
    # 1:1 — одно объявление может иметь не более одной транзакции.
    # PROTECT — нельзя удалить объявление, по которому есть покупка,
    # иначе потеряется история покупок.
    listing = models.OneToOneField(
        ItemListing,
        on_delete=models.PROTECT,
        related_name='transaction',
    )
    # 1:N — один покупатель может совершить несколько покупок.
    # PROTECT — нельзя удалить пользователя, у которого есть покупки
    # (для «удаления» аккаунта используйте is_active=False).
    buyer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='purchases',
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.listing_id and self.buyer_id and self.listing.seller_id == self.buyer_id:
            raise ValidationError({'buyer': 'The seller cannot buy their own listing.'})

    def __str__(self):
        return f"Transaction {self.id} - {self.listing.title}"


class Review(models.Model):
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_left')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    listing = models.ForeignKey(ItemListing, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Review by {self.reviewer} ({self.rating}/5)"