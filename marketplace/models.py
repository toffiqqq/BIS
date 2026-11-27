from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, default='Student')
    # Внутренний баланс студента. У каждого нового пользователя — 10 000 ₸.
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=10000)
    # Номер телефона в формате +7XXXXXXXXXX — по нему регистрируются и входят.
    phone = models.CharField(max_length=16, unique=True, null=True, blank=True)

    @property
    def display_name(self):
        """Имя для показа на сайте: имя пользователя, иначе логин."""
        return self.first_name or self.username

    def __str__(self):
        return self.username


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ItemListing(models.Model):
    CONDITION_CHOICES = [
        ('new', _('New')),
        ('like_new', _('Like new')),
        ('good', _('Good')),
        ('fair', _('Fair')),
    ]

    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='Active') 
    created_at = models.DateTimeField(auto_now_add=True)
    # Картинка товара: путь к файлу в static/ (например
    # "marketplace/img/items/laptop.svg") или полная ссылка https://...
    # Если пусто — показывается заглушка по категории (работает без интернета).
    image_url = models.CharField(max_length=500, blank=True, default='')

    # Описание и общие характеристики. В форме добавления все обязательны;
    # в базе допускают пустые значения только у старых объявлений.
    description = models.TextField(blank=True, default='')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    length_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    width_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

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

    @property
    def dimensions(self):
        """«30 × 20 × 5 см» или пустая строка, если размеры не указаны."""
        sizes = [self.length_cm, self.width_cm, self.height_cm]
        if any(v is None for v in sizes):
            return ''
        return ' × '.join(f'{v.normalize():f}' for v in sizes)

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
    listing = models.ForeignKey(ItemListing, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='reviews')

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # Один отзыв на одну покупку (listing) от одного покупателя.
            models.UniqueConstraint(
                fields=['reviewer', 'listing'],
                condition=models.Q(listing__isnull=False),
                name='unique_review_per_purchase',
            ),
        ]

    def clean(self):
        super().clean()
        if self.reviewer_id and self.seller_id and self.reviewer_id == self.seller_id:
            raise ValidationError({'seller': 'You cannot review yourself.'})

    def __str__(self):
        return f"Review by {self.reviewer} ({self.rating}/5)"


class WalletOperation(models.Model):
    """История операций с балансом: пополнение, вывод, покупка, продажа."""
    KIND_CHOICES = [
        ('deposit', _('Top-up')),
        ('withdraw', _('Withdrawal')),
        ('purchase', _('Purchase')),
        ('sale', _('Sale')),
    ]

    # PROTECT — история денег не должна пропадать вместе с пользователем.
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='wallet_operations')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    # Для покупки и продажи — по какому объявлению.
    listing = models.ForeignKey(ItemListing, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='wallet_operations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    @property
    def is_income(self):
        return self.kind in ('deposit', 'sale')

    def __str__(self):
        return f'{self.user} {self.kind} {self.amount}'
