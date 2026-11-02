from django.db import models
from django.contrib.auth.models import AbstractUser
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
    listing = models.ForeignKey(ItemListing, on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    completed_at = models.DateTimeField(auto_now_add=True)

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