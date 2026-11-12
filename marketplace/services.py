"""Бизнес-логика покупки товара.

Вынесена из views, чтобы одна и та же проверенная логика использовалась
и при покупке покупателем (buy_item), и при отметке продавцом (mark_as_sold).
"""
from django.db import IntegrityError, transaction

from .models import ItemListing, Transaction


class PurchaseError(Exception):
    """Покупку нельзя выполнить (свой товар, уже продан и т. п.)."""


def purchase_listing(listing_id, buyer):
    """Атомарно продаёт объявление покупателю `buyer`.

    1. Блокирует строку объявления (SELECT ... FOR UPDATE), чтобы два
       одновременных запроса не смогли купить один товар.
    2. Проверяет, что покупатель не является продавцом и товар ещё не продан.
    3. Меняет статус на 'Sold' и создаёт Transaction в одной транзакции БД:
       если создание транзакции упадёт, статус откатится.
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

            listing.status = 'Sold'
            listing.save(update_fields=['status'])
            return Transaction.objects.create(listing=listing, buyer=buyer)
    except IntegrityError as exc:
        # Последняя линия защиты: уникальный индекс на transaction.listing_id.
        raise PurchaseError('This item has already been sold.') from exc
