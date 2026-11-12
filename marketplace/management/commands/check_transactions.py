"""Read-only проверка целостности транзакций. Ничего не изменяет в базе.

    python manage.py check_transactions
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, F

from marketplace.models import ItemListing, Transaction


class Command(BaseCommand):
    help = "Report data problems in transactions (read-only, changes nothing)."

    def handle(self, *args, **options):
        problems = 0

        dups = (Transaction.objects.values('listing_id')
                .annotate(n=Count('id')).filter(n__gt=1))
        for row in dups:
            problems += 1
            self.stdout.write(f"DUPLICATE: listing {row['listing_id']} has {row['n']} transactions")

        for tx in Transaction.objects.filter(buyer_id=F('listing__seller_id')).select_related('listing'):
            problems += 1
            self.stdout.write(
                f"SELF-PURCHASE: transaction {tx.id} — seller is the buyer of listing {tx.listing_id} "
                f"(created by the old mark_as_sold logic)"
            )

        for item in ItemListing.objects.filter(status='Sold', transaction__isnull=True):
            problems += 1
            self.stdout.write(f"SOLD WITHOUT TRANSACTION: listing {item.id}")

        for tx in Transaction.objects.exclude(listing__status='Sold'):
            problems += 1
            self.stdout.write(f"TRANSACTION ON UNSOLD LISTING: transaction {tx.id}, listing {tx.listing_id}")

        if problems:
            self.stdout.write(self.style.WARNING(f"{problems} problem(s) found. Nothing was changed."))
        else:
            self.stdout.write(self.style.SUCCESS("No problems found."))
