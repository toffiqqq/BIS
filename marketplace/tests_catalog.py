"""Тесты каталога: фильтры, hero-баннер, локальные ресурсы (без CDN)."""
from decimal import Decimal

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .models import Category, ItemListing, User
from .templatetags.marketplace_extras import category_image


class CatalogFilterTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user(username='seller', password='StrongPassword123!')
        self.books = Category.objects.create(name='Textbooks')
        self.tech = Category.objects.create(name='Electronics')
        self.cheap_book = self._item('Cheap Book', 1000, self.books, seller)
        self.pricey_book = self._item('Pricey Book', 9000, self.books, seller)
        self.laptop = self._item('Laptop', 50000, self.tech, seller)
        self.sold = self._item('Sold Phone', 20000, self.tech, seller, status='Sold')
        self.url = reverse('item_list')

    @staticmethod
    def _item(title, price, category, seller, status='Active'):
        return ItemListing.objects.create(
            title=title, price=Decimal(price), category=category, seller=seller, status=status,
        )

    def _items(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return set(response.context['items'])

    def test_no_filters_shows_all_active_items(self):
        self.assertEqual(self._items(), {self.cheap_book, self.pricey_book, self.laptop})

    def test_filter_by_category(self):
        self.assertEqual(self._items(category=self.tech.pk), {self.laptop})

    def test_filter_by_min_price(self):
        self.assertEqual(self._items(min_price=5000), {self.pricey_book, self.laptop})

    def test_filter_by_max_price(self):
        self.assertEqual(self._items(max_price=9000), {self.cheap_book, self.pricey_book})

    def test_filters_combine_with_search(self):
        found = self._items(q='book', category=self.books.pk, min_price=2000, max_price=10000)
        self.assertEqual(found, {self.pricey_book})

    def test_reversed_price_range_is_swapped(self):
        self.assertEqual(self._items(min_price=10000, max_price=1000), {self.cheap_book, self.pricey_book})

    def test_invalid_filter_values_are_ignored(self):
        found = self._items(category='abc', min_price='lots', max_price='-5')
        self.assertEqual(found, {self.cheap_book, self.pricey_book, self.laptop})

    def test_unknown_category_id_is_ignored(self):
        self.assertEqual(self._items(category=999999), {self.cheap_book, self.pricey_book, self.laptop})

    def test_selected_values_are_kept_in_form(self):
        response = self.client.get(self.url, {'category': self.tech.pk, 'min_price': '100', 'max_price': '60000'})
        self.assertEqual(response.context['selected_category'], self.tech.pk)
        self.assertContains(response, 'name="min_price"')
        self.assertContains(response, 'value="100"')


class HeroAndStaticTests(TestCase):
    def setUp(self):
        self.url = reverse('item_list')
        for name in ('Textbooks', 'Electronics', 'Furniture', 'Clothing', 'Sports'):
            Category.objects.create(name=name)

    def test_hero_with_four_category_tiles_on_clean_home(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="hero"')
        self.assertEqual(len(response.context['hero_categories']), 4)
        self.assertContains(response, 'class="tile"', count=4)

    def test_hero_hidden_when_searching_or_filtering(self):
        self.assertNotContains(self.client.get(self.url, {'q': 'book'}), 'class="hero"')
        self.assertNotContains(self.client.get(self.url, {'min_price': '10'}), 'class="hero"')

    def test_no_external_cdn_and_local_css_linked(self):
        for name in ('item_list', 'login', 'register'):
            html = self.client.get(reverse(name)).content.decode()
            self.assertNotIn('cdn.jsdelivr.net', html)
            self.assertNotIn('bootstrap', html.lower())
            self.assertIn('marketplace/css/style.css', html)

    def test_static_files_exist(self):
        self.assertIsNotNone(finders.find('marketplace/css/style.css'))
        self.assertIsNotNone(finders.find('marketplace/js/main.js'))
        self.assertIsNotNone(finders.find('marketplace/img/categories/default.svg'))

    def test_category_image_mapping_and_fallback(self):
        self.assertTrue(category_image('Textbooks').endswith('books.svg'))
        self.assertTrue(category_image('Учебники').endswith('books.svg'))
        self.assertTrue(category_image('Electronics').endswith('electronics.svg'))
        self.assertTrue(category_image('Something unknown').endswith('default.svg'))
        self.assertTrue(category_image(None).endswith('default.svg'))
