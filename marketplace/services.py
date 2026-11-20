"""Бизнес-логика покупки товара.

Вынесена из views, чтобы одна и та же проверенная логика использовалась
и при покупке покупателем (buy_item), и при отметке продавцом (mark_as_sold).
"""
from django.db import IntegrityError, transaction
from django.db.models import F

from .models import ItemListing, Transaction, User


class PurchaseError(Exception):
    """Покупку нельзя выполнить (свой товар, уже продан и т. п.)."""


def purchase_listing(listing_id, buyer, charge=True):
    """Атомарно продаёт объявление покупателю `buyer`.

    1. Блокирует строку объявления (SELECT ... FOR UPDATE), чтобы два
       одновременных запроса не смогли купить один товар.
    2. Проверяет, что покупатель не является продавцом и товар ещё не продан.
    3. Если charge=True — проверяет баланс покупателя, списывает цену
       и зачисляет её продавцу (строки обоих пользователей тоже блокируются).
    4. Меняет статус на 'Sold' и создаёт Transaction в одной транзакции БД:
       если что-то упадёт, откатятся и статус, и балансы.

    charge=False используется, когда продавец отмечает сделку, оплаченную
    при встрече (mark_as_sold): балансы не меняются.
    """
    try:
        with transaction.atomic():
            listing = ItemListing.objects.select_for_update().get(pk=listing_id)

            if listing.seller_id == buyer.pk:
                raise PurchaseError('You cannot buy your own listing.')
            if listing.status == 'Sold' or Transaction.objects.filter(listing=listing).exists():
                raise PurchaseError('This item has already been sold.')
            if listing.status != 'Active':
                raise PurchaseError('This item is not available for purchase.')

            if charge:
                # Блокируем обоих пользователей в одном порядке (по id) — без взаимных блокировок.
                users = {u.pk: u for u in User.objects.select_for_update()
                         .filter(pk__in=[buyer.pk, listing.seller_id]).order_by('pk')}
                if users[buyer.pk].balance < listing.price:
                    raise PurchaseError('Not enough money on your balance.')
                User.objects.filter(pk=buyer.pk).update(balance=F('balance') - listing.price)
                User.objects.filter(pk=listing.seller_id).update(balance=F('balance') + listing.price)

            listing.status = 'Sold'
            listing.save(update_fields=['status'])
            return Transaction.objects.create(listing=listing, buyer=buyer)
    except IntegrityError as exc:
        # Последняя линия защиты: уникальный индекс на transaction.listing_id.
        raise PurchaseError('This item has already been sold.') from exc


# ---------------------------------------------------------------------------
# Отзывы
# ---------------------------------------------------------------------------

class ReviewError(Exception):
    """Отзыв оставить нельзя (не покупатель, уже оставлен, отзыв себе и т. п.)."""


def reviewable_purchases(reviewer, seller):
    """Покупки `reviewer` у продавца `seller`, на которые ещё нет отзыва.

    Отзыв можно оставить только после завершённой покупки: ищем транзакции,
    где reviewer — покупатель, а seller — продавец объявления.
    """
    from .models import Review  # локальный импорт, чтобы не было циклов

    if reviewer is None or not reviewer.is_authenticated or reviewer.pk == seller.pk:
        return Transaction.objects.none()
    reviewed_listing_ids = Review.objects.filter(
        reviewer=reviewer, listing__isnull=False).values('listing_id')
    return (Transaction.objects
            .filter(buyer=reviewer, listing__seller=seller)
            .exclude(listing_id__in=reviewed_listing_ids)
            .select_related('listing')
            .order_by('-completed_at'))


def leave_review(reviewer, seller, listing_id, rating, comment):
    """Создаёт отзыв, проверяя все бизнес-правила."""
    from .models import Review

    if reviewer.pk == seller.pk:
        raise ReviewError('You cannot review yourself.')
    tx = reviewable_purchases(reviewer, seller).filter(listing_id=listing_id).first()
    if tx is None:
        raise ReviewError('You can only review a seller after buying from them, once per purchase.')
    try:
        with transaction.atomic():
            return Review.objects.create(
                reviewer=reviewer, seller=seller, listing=tx.listing,
                rating=rating, comment=comment)
    except IntegrityError as exc:
        raise ReviewError('You have already reviewed this purchase.') from exc
