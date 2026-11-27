"""Наполняет базу стартовыми данными: категории, пользователи, объявления.

    python manage.py seed_demo

Команду можно запускать повторно: уже существующие записи не дублируются
и не изменяются. Чужие данные в базе команда не удаляет.

Тестовые пользователи входят по номеру телефона (см. USERS). Код в демо-режиме
показывается на странице ввода кода. Переменная DEMO_PASSWORD — пароль для
входа в тестах и через shell (по умолчанию Demo12345!).

Если объявление или пользователь уже есть, но без описания, характеристик
или номера телефона (база создана старой версией), эти поля дозаполняются.
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
    # username, student_id, first name, last name, phone
    ('aruzhan', '23B030101', 'Aruzhan', 'Sarsenova', '+77010000001'),
    ('dias', '23B030102', 'Dias', 'Nurlanov', '+77010000002'),
    ('madina', '24B030103', 'Madina', 'Akhmetova', '+77010000003'),
    ('timur', '22B030104', 'Timur', 'Bekov', '+77010000004'),
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

# title: (description, condition, weight kg, length, width, height cm)
DETAILS = {
    "Thomas' Calculus, 14th edition": ('Hardcover, all pages in place, a few pencil notes in chapters 2–4. Covers the full first-year calculus course.', 'good', '2.1', '28', '22', '4.5'),
    'University Physics (Young & Freedman)': ('15th edition, used for one semester. Clean pages, slightly worn corners.', 'good', '2.6', '28', '22', '5'),
    'English Grammar in Use': ('Intermediate level with answers. Exercises filled in pencil, easy to erase.', 'fair', '0.7', '25', '19', '1.5'),
    'Set of 4 programming books': ('Python, Algorithms, Clean Code and SQL basics. Sold together as a set.', 'good', '3.4', '24', '17', '12'),
    'Discrete Mathematics (Rosen)': ('7th edition, softcover. No notes, no torn pages.', 'like_new', '1.6', '26', '20', '3.5'),
    'Lenovo IdeaPad 3, 8 GB RAM': ('Ryzen 5, 8 GB RAM, 256 GB SSD, 15.6" screen. Battery holds about 5 hours. Comes with the charger.', 'good', '1.7', '36', '24', '2'),
    'Wireless headphones': ('Bluetooth 5.0, noise isolation, up to 20 hours of battery. Cable and case included.', 'like_new', '0.25', '18', '16', '7'),
    'Casio fx-991EX calculator': ('Scientific calculator, allowed on university exams. Works perfectly, with cover.', 'like_new', '0.1', '16', '8', '1.1'),
    'Samsung Galaxy A14': ('64 GB, black. Screen protector since day one, no scratches. Box and charger included.', 'good', '0.2', '17', '8', '0.9'),
    '24" monitor, Full HD': ('1920×1080, 75 Hz, HDMI and VGA. No dead pixels. Stand included.', 'good', '3.2', '54', '32', '5'),
    'Pack of 5 notebooks': ('A5, 96 sheets each, grid. New, still in the wrapping.', 'new', '0.9', '21', '15', '4'),
    'Colored pencils, 24 pcs': ('Full set of 24 colours, sharpened once. Metal box.', 'like_new', '0.3', '19', '18', '1'),
    'Laptop backpack': ('Fits laptops up to 15.6". Waterproof, two main compartments, USB port.', 'good', '0.8', '45', '30', '15'),
    'Electric kettle 1.7 L': ('Stainless steel, auto shut-off. Descaled, works fine.', 'good', '1.1', '23', '16', '25'),
    'Desk lamp with LED': ('3 brightness levels, flexible neck, USB powered.', 'like_new', '0.6', '40', '15', '15'),
    'Ceramic mug': ('350 ml, white with the university logo. No chips.', 'new', '0.35', '12', '9', '10'),
    'Linear Algebra textbook': ('Gilbert Strang, 5th edition. Clean, no notes.', 'good', '1.2', '24', '18', '3'),
    'USB mouse': ('Wired optical mouse, 1.5 m cable. Works on any surface.', 'good', '0.1', '12', '6', '4'),
    'Study lamp': ('Warm light, metal base, 1.5 m cable.', 'fair', '0.9', '45', '15', '15'),
}

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
        for username, sid, first, last, phone in USERS:
            user = User.objects.filter(username=username).first()
            phone_free = not User.objects.filter(phone=phone).exclude(username=username).exists()
            if user is None:
                if User.objects.filter(student_id=sid).exists():
                    sid = None  # такой student_id уже занят реальным пользователем
                user = User.objects.create_user(
                    username, f'{username}@example.com', demo_password,
                    student_id=sid, first_name=first, last_name=last,
                    phone=phone if phone_free else None)
                created['users'] += 1
            elif not user.phone and phone_free:
                user.phone = phone
                user.save(update_fields=['phone'])
            users[username] = user

        listings = {}
        for title, price, cat, seller, pic in ITEMS:
            item, was_created = ItemListing.objects.get_or_create(
                title=title, seller=users[seller],
                defaults={'price': price, 'category': cats[cat],
                          'image_url': f'marketplace/img/items/{pic}.svg'})
            listings[title] = item
            created['items'] += was_created
            if not item.description:
                desc, cond, weight, length, width, height = DETAILS[title]
                item.description, item.condition = desc, cond
                item.weight_kg, item.length_cm, item.width_cm, item.height_cm = weight, length, width, height
                item.save(update_fields=['description', 'condition', 'weight_kg',
                                         'length_cm', 'width_cm', 'height_cm'])

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
            self.stdout.write('  Log in by phone: ' + ', '.join(f'{u[0]} {u[4]}' for u in USERS))
