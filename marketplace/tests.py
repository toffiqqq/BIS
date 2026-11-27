from unittest import mock

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError, RestrictedError
from django.test import TestCase, Client
from django.urls import reverse

from .models import User, Category, ItemListing, Transaction, Review
from .forms import ItemListingForm, PhoneRegisterForm
from .services import PurchaseError, purchase_listing


class StudentMarketplaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user(
            username='alex_test',
            email='alex_test@kbtu.kz',
            password='StrongPassword123!',
            student_id='24B000001'
        )
        self.other_student = User.objects.create_user(
            username='maria_test',
            email='maria_test@kbtu.kz',
            password='StrongPassword123!',
            student_id='24B000002'
        )
        self.category = Category.objects.create(name='Textbooks')

    def test_tc01_negative_or_zero_price_rejected(self):
        form = ItemListingForm(data={
            'title': 'Calculus Textbook',
            'price': -500,
            'category': self.category.id
        })
        form.user = self.seller
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_tc02_excessive_price_rejected(self):
        form = ItemListingForm(data={
            'title': 'Expensive Laptop',
            'price': 150000,
            'category': self.category.id
        })
        form.user = self.seller
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_tc03_max_10_active_listings_limit(self):
        for i in range(10):
            ItemListing.objects.create(
                title=f'Item {i}',
                price=1000,
                status='Active',
                seller=self.seller,
                category=self.category
            )

        form = ItemListingForm(data={
            'title': '11th Item',
            'price': 2000,
            'category': self.category.id,
            # Описание и характеристики обязательны — заполняем, чтобы форму
            # отклонил именно лимит в 10 объявлений.
            'description': 'Good condition, used one semester.',
            'condition': 'good', 'weight_kg': 1, 'length_cm': 20, 'width_cm': 15, 'height_cm': 3,
        })
        form.user = self.seller
        self.assertFalse(form.is_valid())
        self.assertIn('10 active listings', str(form.non_field_errors()))

    def test_tc04_search_across_three_entities(self):
        from django.db.models import Q
        item = ItemListing.objects.create(
            title='Thomas Calculus',
            price=4500,
            status='Active',
            seller=self.seller,
            category=self.category
        )
        for query in ['Calculus', 'alex_test', 'Textbooks']:
            results = ItemListing.objects.filter(status='Active').filter(
                Q(title__icontains=query) |
                Q(seller__username__icontains=query) |
                Q(category__name__icontains=query)
            )
            self.assertIn(item, results)

    def test_tc05_mark_as_sold_creates_transaction(self):
        item = ItemListing.objects.create(
            title='Physics Book',
            price=3000,
            status='Active',
            seller=self.seller,
            category=self.category
        )
        self.client.login(username='alex_test', password='StrongPassword123!')
        # The seller must name the buyer; the seller can no longer be the buyer.
        self.client.post(reverse('mark_as_sold', args=[item.id]), {'buyer': 'maria_test'})

        item.refresh_from_db()
        self.assertEqual(item.status, 'Sold')
        self.assertEqual(Transaction.objects.filter(listing=item).count(), 1)
        self.assertEqual(item.transaction.buyer, self.other_student)

    def test_tc06_unauthenticated_redirect_on_add_item(self):
        response = self.client.get(reverse('add_item'))
        self.assertEqual(response.status_code, 302)

    def test_tc07_cannot_mark_other_user_item_as_sold(self):
        item = ItemListing.objects.create(
            title='Graphing Calculator',
            price=5000,
            status='Active',
            seller=self.seller,
            category=self.category
        )
        self.client.login(username='maria_test', password='StrongPassword123!')
        response = self.client.get(reverse('mark_as_sold', args=[item.id]))
        self.assertEqual(response.status_code, 404)

    def test_tc08_restrict_prevents_orphan_records(self):
        ItemListing.objects.create(
            title='Linear Algebra',
            price=2500,
            status='Active',
            seller=self.seller,
            category=self.category
        )
        with self.assertRaises(RestrictedError):
            self.category.delete()

    def test_tc09_student_registration_and_unique_student_id(self):
        # Регистрация теперь по номеру телефона; Student ID по-прежнему уникален.
        valid_form = PhoneRegisterForm(data={
            'phone': '+7 701 555 00 03', 'first_name': 'New Student', 'student_id': '24B000003',
        })
        self.assertTrue(valid_form.is_valid(), valid_form.errors)
        self.assertEqual(valid_form.cleaned_data['phone'], '+77015550003')

        duplicate_form = PhoneRegisterForm(data={
            'phone': '+7 701 555 00 04', 'first_name': 'Another', 'student_id': '24B000001',
        })
        self.assertFalse(duplicate_form.is_valid())
        self.assertIn('student_id', duplicate_form.errors)

    def test_tc10_admin_panel_removed(self):
        # Админ-панели на сайте нет: /admin/ не существует ни для студента, ни для суперпользователя.
        self.client.login(username='alex_test', password='StrongPassword123!')
        self.assertEqual(self.client.get('/admin/').status_code, 404)
        User.objects.create_superuser(username='admin_test', password='StrongPassword123!', student_id='24B000099')
        self.client.login(username='admin_test', password='StrongPassword123!')
        self.assertEqual(self.client.get('/admin/').status_code, 404)


class RelationshipAndPurchaseTests(TestCase):
    """Student 3: внешние ключи, связи между таблицами и логика покупки."""

    PASSWORD = 'StrongPassword123!'

    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller_fk', password=self.PASSWORD, student_id='24B100001')
        self.buyer = User.objects.create_user(
            username='buyer_fk', password=self.PASSWORD, student_id='24B100002')
        self.category = Category.objects.create(name='Electronics')

    def make_listing(self, title='Item', seller=None, status='Active'):
        return ItemListing.objects.create(
            title=title, price=1000, status=status,
            seller=seller or self.seller, category=self.category)

    # 1. USERS -> ITEM_LISTING (1:N)
    def test_01_user_can_create_multiple_listings(self):
        a = self.make_listing('Laptop')
        b = self.make_listing('Mouse')
        c = self.make_listing('Keyboard')
        self.assertEqual(self.seller.listings.count(), 3)
        self.assertCountEqual(self.seller.listings.all(), [a, b, c])

    # 2.
    def test_02_each_listing_has_correct_seller(self):
        mine = self.make_listing('Mine')
        theirs = self.make_listing('Theirs', seller=self.buyer)
        self.assertEqual(mine.seller, self.seller)
        self.assertEqual(theirs.seller, self.buyer)
        self.assertNotIn(theirs, self.seller.listings.all())

    # 3. ITEM_LISTING -> TRANSACTIONS (1:1)
    def test_03_listing_has_at_most_one_transaction(self):
        listing = self.make_listing()
        Transaction.objects.create(listing=listing, buyer=self.buyer)
        other_buyer = User.objects.create_user(username='buyer2', password=self.PASSWORD)
        # Database-level unique constraint on transaction.listing_id
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(listing=listing, buyer=other_buyer)
        self.assertEqual(Transaction.objects.filter(listing=listing).count(), 1)
        listing = ItemListing.objects.get(pk=listing.pk)
        self.assertEqual(listing.transaction.buyer, self.buyer)

    def test_03b_listing_field_is_one_to_one_protect(self):
        field = Transaction._meta.get_field('listing')
        self.assertTrue(field.one_to_one)
        from django.db.models import PROTECT
        self.assertIs(field.remote_field.on_delete, PROTECT)
        self.assertIs(Transaction._meta.get_field('buyer').remote_field.on_delete, PROTECT)

    # 4. USERS -> TRANSACTIONS (1:N)
    def test_04_buyer_can_have_multiple_transactions(self):
        for i in range(3):
            purchase_listing(self.make_listing(f'Item {i}').id, buyer=self.buyer)
        self.assertEqual(self.buyer.purchases.count(), 3)

    # 5.
    def test_05_cannot_delete_seller_with_listings(self):
        self.make_listing()
        with self.assertRaises(RestrictedError):
            self.seller.delete()
        self.assertTrue(User.objects.filter(pk=self.seller.pk).exists())

    def test_05b_cannot_delete_buyer_with_purchases(self):
        purchase_listing(self.make_listing().id, buyer=self.buyer)
        with self.assertRaises(ProtectedError):
            self.buyer.delete()
        self.assertEqual(Transaction.objects.count(), 1)

    # 6.
    def test_06_cannot_delete_listing_referenced_by_transaction(self):
        listing = self.make_listing()
        purchase_listing(listing.id, buyer=self.buyer)
        with self.assertRaises(ProtectedError):
            listing.delete()
        self.assertTrue(ItemListing.objects.filter(pk=listing.pk).exists())
        self.assertEqual(Transaction.objects.count(), 1)

    # 7.
    def test_07_cannot_buy_own_item_service(self):
        listing = self.make_listing()
        with self.assertRaises(PurchaseError):
            purchase_listing(listing.id, buyer=self.seller)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'Active')
        self.assertFalse(Transaction.objects.exists())

    def test_07b_cannot_buy_own_item_via_views(self):
        listing = self.make_listing()
        self.client.login(username='seller_fk', password=self.PASSWORD)
        self.client.post(reverse('buy_item', args=[listing.id]))
        self.client.post(reverse('mark_as_sold', args=[listing.id]), {'buyer': 'seller_fk'})
        # Old behaviour: a bare GET made the seller the buyer.
        self.client.get(reverse('mark_as_sold', args=[listing.id]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'Active')
        self.assertFalse(Transaction.objects.exists())

    def test_07c_model_validation_rejects_self_purchase(self):
        listing = self.make_listing()
        with self.assertRaises(ValidationError):
            Transaction(listing=listing, buyer=self.seller).full_clean()

    # 8.
    def test_08_cannot_buy_sold_item_again(self):
        listing = self.make_listing()
        purchase_listing(listing.id, buyer=self.buyer)
        other_buyer = User.objects.create_user(username='late_buyer', password=self.PASSWORD)
        with self.assertRaises(PurchaseError):
            purchase_listing(listing.id, buyer=other_buyer)
        with self.assertRaises(PurchaseError):
            purchase_listing(listing.id, buyer=self.buyer)
        self.assertEqual(Transaction.objects.filter(listing=listing).count(), 1)
        self.assertEqual(listing.transaction.buyer, self.buyer)

    def test_08b_cannot_buy_sold_item_again_via_view(self):
        listing = self.make_listing()
        self.client.login(username='buyer_fk', password=self.PASSWORD)
        self.client.post(reverse('buy_item', args=[listing.id]))
        response = self.client.post(reverse('buy_item', args=[listing.id]))
        self.assertEqual(Transaction.objects.filter(listing=listing).count(), 1)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn('This item has already been sold.', messages)

    # 9.
    def test_09_status_unchanged_when_transaction_creation_fails(self):
        listing = self.make_listing()
        with mock.patch.object(Transaction.objects, 'create', side_effect=DatabaseError('boom')):
            with self.assertRaises(DatabaseError):
                purchase_listing(listing.id, buyer=self.buyer)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'Active')
        self.assertFalse(Transaction.objects.exists())

    # Correct flow end-to-end
    def test_10_buyer_purchases_item_via_view(self):
        listing = self.make_listing()
        self.client.login(username='buyer_fk', password=self.PASSWORD)
        response = self.client.post(reverse('buy_item', args=[listing.id]))
        self.assertRedirects(response, reverse('item_list'), fetch_redirect_response=False)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'Sold')
        self.assertEqual(listing.transaction.buyer, self.buyer)
        self.assertEqual(listing.seller, self.seller)

    def test_11_buy_requires_post_and_login(self):
        listing = self.make_listing()
        self.assertEqual(self.client.post(reverse('buy_item', args=[listing.id])).status_code, 302)
        self.client.login(username='buyer_fk', password=self.PASSWORD)
        self.assertEqual(self.client.get(reverse('buy_item', args=[listing.id])).status_code, 405)
        self.assertFalse(Transaction.objects.exists())

    def test_12_mark_as_sold_without_buyer_changes_nothing(self):
        listing = self.make_listing()
        self.client.login(username='seller_fk', password=self.PASSWORD)
        self.client.post(reverse('mark_as_sold', args=[listing.id]))
        self.client.post(reverse('mark_as_sold', args=[listing.id]), {'buyer': 'nobody'})
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'Active')
        self.assertFalse(Transaction.objects.exists())


class BalanceTests(TestCase):
    """Баланс: 10 000 ₸ при регистрации, списание у покупателя и зачисление продавцу."""

    PASSWORD = 'StrongPassword123!'

    def setUp(self):
        self.seller = User.objects.create_user(username='seller_b', password=self.PASSWORD)
        self.buyer = User.objects.create_user(username='buyer_b', password=self.PASSWORD)
        self.category = Category.objects.create(name='Electronics')

    def item(self, price):
        return ItemListing.objects.create(title=f'Item {price}', price=price, seller=self.seller, category=self.category)

    def test_new_user_starts_with_10000(self):
        self.assertEqual(self.buyer.balance, 10000)
        self.client.post(reverse('register'), {'phone': '+7 702 000 11 22', 'first_name': 'Fresh'})
        code = self.client.session['phone_verification']['demo_code']
        self.client.post(reverse('verify_phone'), {'code': code})
        self.assertEqual(User.objects.get(phone='+77020001122').balance, 10000)

    def test_purchase_moves_money_from_buyer_to_seller(self):
        purchase_listing(self.item(3500).id, buyer=self.buyer)
        self.buyer.refresh_from_db(); self.seller.refresh_from_db()
        self.assertEqual(self.buyer.balance, 6500)
        self.assertEqual(self.seller.balance, 13500)

    def test_not_enough_money(self):
        expensive = self.item(15000)
        with self.assertRaises(PurchaseError):
            purchase_listing(expensive.id, buyer=self.buyer)
        expensive.refresh_from_db(); self.buyer.refresh_from_db()
        self.assertEqual(expensive.status, 'Active')
        self.assertEqual(self.buyer.balance, 10000)
        self.assertFalse(Transaction.objects.exists())

    def test_not_enough_money_via_view(self):
        expensive = self.item(15000)
        self.client.login(username='buyer_b', password=self.PASSWORD)
        r = self.client.get(reverse('item_detail', args=[expensive.id]))
        self.assertContains(r, 'Not enough money')
        self.assertNotContains(r, reverse('buy_item', args=[expensive.id]))
        r = self.client.post(reverse('buy_item', args=[expensive.id]))
        self.assertIn('Not enough money on your balance.', [str(m) for m in get_messages(r.wsgi_request)])
        self.assertFalse(Transaction.objects.exists())

    def test_balance_restored_if_purchase_fails(self):
        listing = self.item(2000)
        with mock.patch.object(Transaction.objects, 'create', side_effect=DatabaseError('boom')):
            with self.assertRaises(DatabaseError):
                purchase_listing(listing.id, buyer=self.buyer)
        self.buyer.refresh_from_db(); self.seller.refresh_from_db()
        self.assertEqual((self.buyer.balance, self.seller.balance), (10000, 10000))

    def test_mark_as_sold_in_person_does_not_charge(self):
        listing = self.item(4000)
        self.client.login(username='seller_b', password=self.PASSWORD)
        self.client.post(reverse('mark_as_sold', args=[listing.id]), {'buyer': 'buyer_b'})
        listing.refresh_from_db(); self.buyer.refresh_from_db()
        self.assertEqual(listing.status, 'Sold')
        self.assertEqual(self.buyer.balance, 10000)

    def test_balance_shown_in_header_and_profile(self):
        self.client.login(username='buyer_b', password=self.PASSWORD)
        r = self.client.get(reverse('profile'))
        self.assertContains(r, '10,000 ₸')
