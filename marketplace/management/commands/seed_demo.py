"""Наполняет базу стартовыми данными: категории, пользователи, объявления.

    python manage.py seed_demo

Команду можно запускать повторно: уже существующие записи не дублируются
и не изменяются. Чужие данные в базе команда не удаляет.

Переменная окружения DEMO_PASSWORD — пароль тестовых пользователей
(по умолчанию Demo12345!).
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from marketplace.models import Category, ItemListing, Review, Transaction, User
from marketplace.services import purchase_listing


CATEGORIES = [
    ('Textbooks', 'University textbooks and study guides'),
    ('Electronics', 'Laptops, phones, headphones, calculators'),
    ('Stationery', 'Notebooks, pens, backpacks and supplies'),
    ('Household', 'Things for the dorm: kettles, lamps, mugs'),
]

USERS = [
    # username, student_id, first name, last name
    ('aruzhan', '23B030101', 'Aruzhan', 'Sarsenova'),
    ('dias', '23B030102', 'Dias', 'Nurlanov'),
    ('madina', '24B030103', 'Madina', 'Akhmetova'),
    ('timur', '22B030104', 'Timur', 'Bekov'),
]

# title, price, category, seller, picture (static/marketplace/img/items/<pic>.svg)
ITEMS = [
    ('Thomas\' Calculus, 14th edition', 4500, 'Textbooks', 'aruzhan', 'textbook'),
    ('University Physics (Young & Freedman)', 5200, 'Textbooks', 'timur', 'physics'),
    ('English Grammar in Use', 2500, 'Textbooks', 'madina', 'english'),
    ('Set of 4 programming books', 7000, 'Textbooks', 'dias', 'books'),
    ('Discrete Mathematics (Rosen)', 3800, 'Textbooks', 'aruzhan', 'textbook'),
    ('Lenovo IdeaPad 3, 8 GB RAM', 95000, 'Electronics', 'timur', 'laptop'),
    ('Wireless headphones', 12000, 'Electronics', 'madina', 'headphones'),
    ('Casio fx-991EX calculator', 6500, 'Electronics', 'dias', 'calculator'),
    ('Samsung Galaxy A14', 38000, 'Electronics', 'aruzhan', 'phone'),
    ('24" monitor, Full HD', 32000, 'Electronics', 'timur', 'monitor'),
    ('Pack of 5 notebooks', 1500, 'Stationery', 'madina', 'notebook'),
    ('Colored pencils, 24 pcs', 1200, 'Stationery', 'aruzhan', 'pencils'),
    ('Laptop backpack', 8500, 'Stationery', 'dias', 'backpack'),
    ('Electric kettle 1.7 L', 4000, 'Household', 'timur', 'kettle'),
    ('Desk lamp with LED', 3500, 'Household', 'madina', 'lamp'),
    ('Ceramic mug', 900, 'Household', 'dias', 'mug'),
    # Эти товары будут проданы (см. SALES)
    ('Linear Algebra textbook', 3000, 'Textbooks', 'aruzhan', 'textbook'),
    ('USB mouse', 2000, 'Electronics', 'aruzhan', 'box'),
    ('Study lamp', 2800, 'Household', 'timur', 'lamp'),
]

# (title, buyer)
SALES = [
    ('Linear Algebra textbook', 'dias'),
    ('USB mouse', 'dias'),
    ('Study lamp', 'madina'),
]

# (reviewer, listing title, rating, comment) — у dias остаётся одна покупка без отзыва для показа
REVIEWS = [
    ('dias', 'Linear Algebra textbook', 5, 'Book in great condition, met at the university entrance. Recommend!'),
    ('madina', 'Study lamp', 4, 'Works fine, the seller was polite. A small scratch on the base.'),
]


class Command(BaseCommand):
    help = 'Create demo users, categories, listings, purchases and reviews (safe to re-run).'

    @transaction.atomic
    def handle(self, *args, **options):
        created = {'users': 0, 'items': 0, 'sales': 0, 'reviews': 0}

        demo_password = os.getenv('DEMO_PASSWORD', 'Demo12345!')

        cats = {}
        for name, desc in CATEGORIES:
            cats[name], _ = Category.objects.get_or_create(name=name, defaults={'description': desc})

        users = {}
        for username, sid, first, last in USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                if User.objects.filter(student_id=sid).exists():
                    sid = None  # такой student_id уже занят реальным пользователем
                user = User.objects.create_user(
                    username, f'{username}@example.com', demo_password,
                    student_id=sid, first_name=first, last_name=last)
                created['users'] += 1
            users[username] = user

        listings = {}
        for title, price, cat, seller, pic in ITEMS:
            item, was_created = ItemListing.objects.get_or_create(
                title=title, seller=users[seller],
                defaults={'price': price, 'category': cats[cat],
                          'image_url': f'marketplace/img/items/{pic}.svg'})
            listings[title] = item
            created['items'] += was_created

        for title, buyer in SALES:
            item = listings[title]
            if not Transaction.objects.filter(listing=item).exists() and item.status == 'Active':
                purchase_listing(item.id, buyer=users[buyer])
                created['sales'] += 1

        for reviewer, title, rating, comment in REVIEWS:
            item = listings[title]
            _, was_created = Review.objects.get_or_create(
                reviewer=users[reviewer], listing=item,
                defaults={'seller': item.seller, 'rating': rating, 'comment': comment})
            created['reviews'] += was_created

        self.stdout.write(self.style.SUCCESS(
            'Seed data: +{users} users, +{items} listings, +{sales} sales, +{reviews} reviews.'
            .format(**created)))
        if settings.DEBUG:
            self.stdout.write(f'  Students: aruzhan, dias, madina, timur / {demo_password}')
