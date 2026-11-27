"""Тесты части Student 3: вход по номеру телефона, баланс, характеристики
товара, страница товара, профиль, отзывы и витрина каталога."""
from decimal import Decimal
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from . import phone_auth
from .forms import ItemListingForm
from .models import Category, ItemListing, Review, Transaction, User, WalletOperation
from .services import WalletError, deposit, purchase_listing, withdraw

PASSWORD = 'StrongPassword123!'
DETAILS = {'description': 'Clean copy, no notes inside.', 'condition': 'good',
           'weight_kg': '1.2', 'length_cm': '24', 'width_cm': '17', 'height_cm': '3'}


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class PhoneNormalizeTests(TestCase):
    def test_accepts_common_formats(self):
        for raw in ('+7 701 123 45 67', '8 (701) 123-45-67', '77011234567', '7011234567', '+7-701-123-4567'):
            self.assertEqual(phone_auth.normalize_phone(raw), '+77011234567', raw)

    def test_rejects_bad_numbers(self):
        for raw in ('', '12345', '+1 202 555 0100', 'phone', '9 701 123 45 67'):
            self.assertIsNone(phone_auth.normalize_phone(raw), raw)

    def test_format_for_display(self):
        self.assertEqual(phone_auth.format_phone('+77011234567'), '+7 701 123 45 67')


class PhoneAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u_known', password=PASSWORD,
                                             phone='+77010000001', first_name='Aruzhan')

    def code(self):
        return self.client.session['phone_verification']['demo_code']

    def shift_time(self, **fields):
        """Сдвигает время в данных проверки (код «устарел», кулдаун «прошёл»)."""
        session = self.client.session
        session['phone_verification'].update(fields)
        session.save()

    def test_register_with_phone_and_code(self):
        r = self.client.post(reverse('register'), {'phone': '8 705 555 12 34', 'first_name': 'Aibar',
                                                   'student_id': '23B099999'})
        self.assertRedirects(r, reverse('verify_phone'))
        self.assertFalse(User.objects.filter(phone='+77055551234').exists())  # до кода аккаунта нет

        page = self.client.get(reverse('verify_phone'))
        self.assertContains(page, '+7 705 555 12 34')
        self.assertContains(page, self.code())                                 # демо-код на странице

        r = self.client.post(reverse('verify_phone'), {'code': self.code()})
        self.assertRedirects(r, reverse('item_list'))
        user = User.objects.get(phone='+77055551234')
        self.assertEqual((user.first_name, user.student_id, user.balance), ('Aibar', '23B099999', 10000))
        self.assertFalse(user.has_usable_password())                            # пароля нет
        self.assertNotIn('7055551234', user.username)                           # номер не светится в URL
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_register_rejects_existing_phone_and_bad_phone(self):
        r = self.client.post(reverse('register'), {'phone': '+7 701 000 00 01', 'first_name': 'X'})
        self.assertContains(r, 'already registered')
        r = self.client.post(reverse('register'), {'phone': '123', 'first_name': 'X'})
        self.assertContains(r, 'Enter a phone number')
        self.assertNotIn('phone_verification', self.client.session)

    def test_login_with_phone_and_code(self):
        r = self.client.post(reverse('login'), {'phone': '+7 (701) 000-00-01', 'next': reverse('profile')})
        self.assertRedirects(r, reverse('verify_phone'))
        r = self.client.post(reverse('verify_phone'), {'code': self.code()})
        self.assertRedirects(r, reverse('profile'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_unknown_phone(self):
        r = self.client.post(reverse('login'), {'phone': '+7 777 999 99 99'})
        self.assertContains(r, 'No account with this phone number')

    def test_wrong_code_does_not_log_in(self):
        self.client.post(reverse('login'), {'phone': '+77010000001'})
        good = self.code()
        bad = '0000' if good != '0000' else '1111'
        r = self.client.post(reverse('verify_phone'), {'code': bad})
        self.assertContains(r, 'Wrong code')
        self.assertNotIn('_auth_user_id', self.client.session)
        r = self.client.post(reverse('verify_phone'), {'code': good})               # правильный код ещё работает
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_too_many_wrong_attempts_expire_code(self):
        self.client.post(reverse('login'), {'phone': '+77010000001'})
        good = self.code()
        bad = '0000' if good != '0000' else '1111'
        for _ in range(phone_auth.MAX_ATTEMPTS):
            self.client.post(reverse('verify_phone'), {'code': bad})
        r = self.client.post(reverse('verify_phone'), {'code': good})
        self.assertRedirects(r, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_expired_code(self):
        self.client.post(reverse('login'), {'phone': '+77010000001'})
        code = self.code()
        self.shift_time(expires=0)
        r = self.client.post(reverse('verify_phone'), {'code': code})
        self.assertIn('The code has expired. Request a new one.', messages_of(r))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_resend_gives_new_code_after_cooldown(self):
        self.client.post(reverse('login'), {'phone': '+77010000001'})
        first = self.client.session['phone_verification']['code_hash']
        r = self.client.post(reverse('verify_phone'), {'resend': '1'})
        self.assertIn('Wait 30 seconds before requesting a new code.', messages_of(r))
        self.shift_time(sent_at=0)
        self.client.post(reverse('verify_phone'), {'resend': '1'})
        self.assertNotEqual(self.client.session['phone_verification']['code_hash'], first)

    def test_verify_page_without_request_redirects(self):
        self.assertRedirects(self.client.get(reverse('verify_phone')), reverse('login'))

    @override_settings(PHONE_AUTH_DEMO=False)
    def test_code_hidden_when_demo_mode_off(self):
        self.client.post(reverse('login'), {'phone': '+77010000001'})
        self.assertIsNone(self.client.session['phone_verification']['demo_code'])
        self.assertNotContains(self.client.get(reverse('verify_phone')), 'demo-code')


class WalletTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wallet_u', password=PASSWORD, phone='+77010000009')
        self.client.login(username='wallet_u', password=PASSWORD)

    def test_deposit_and_withdraw_via_profile(self):
        self.client.post(reverse('wallet', args=['deposit']), {'deposit-amount': '5000'})
        self.client.post(reverse('wallet', args=['withdraw']), {'withdraw-amount': '2000'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 13000)
        ops = list(self.user.wallet_operations.values_list('kind', 'amount', 'balance_after'))
        self.assertEqual(ops, [('withdraw', 2000, 13000), ('deposit', 5000, 15000)])
        page = self.client.get(reverse('profile'))
        self.assertContains(page, 'Balance history')
        self.assertContains(page, '+5,000 ₸')

    def test_cannot_withdraw_more_than_balance(self):
        r = self.client.post(reverse('wallet', args=['withdraw']), {'withdraw-amount': '20000'})
        self.assertIn('Not enough money on your balance.', messages_of(r))
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 10000)
        self.assertFalse(WalletOperation.objects.exists())

    def test_amount_limits(self):
        for amount in ('50', '0', '-100', '600000', 'abc'):
            self.client.post(reverse('wallet', args=['deposit']), {'deposit-amount': amount})
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 10000)
        with self.assertRaises(WalletError):
            deposit(self.user, Decimal('99'))

    def test_wallet_requires_post_login_and_known_kind(self):
        self.assertEqual(self.client.get(reverse('wallet', args=['deposit'])).status_code, 405)
        self.client.post(reverse('wallet', args=['steal']), {'steal-amount': '1000'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 10000)
        self.client.logout()
        r = self.client.post(reverse('wallet', args=['deposit']), {'deposit-amount': '1000'})
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r['Location'])

    def test_withdraw_service_directly(self):
        withdraw(self.user, 10000)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, 0)
        with self.assertRaises(WalletError):
            withdraw(self.user, 100)

    def test_purchase_is_recorded_in_both_histories(self):
        seller = User.objects.create_user(username='s_w', password=PASSWORD)
        item = ItemListing.objects.create(title='Lamp', price=3000, seller=seller,
                                          category=Category.objects.create(name='Household'))
        purchase_listing(item.id, buyer=self.user)
        self.assertEqual(self.user.wallet_operations.get().kind, 'purchase')
        sale = seller.wallet_operations.get()
        self.assertEqual((sale.kind, sale.amount, sale.balance_after, sale.listing), ('sale', 3000, 13000, item))


class ItemDetailsTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller_d', password=PASSWORD, first_name='Timur',
                                               phone='+77010000004')
        self.buyer = User.objects.create_user(username='buyer_d', password=PASSWORD, phone='+77010000005')
        self.cat = Category.objects.create(name='Electronics')

    def form(self, **overrides):
        data = {'title': 'Headphones', 'price': 12000, 'category': self.cat.id, **DETAILS, **overrides}
        form = ItemListingForm(data=data)
        form.user = self.seller
        return form

    def test_description_and_specs_are_required(self):
        for name in ('description', 'weight_kg', 'length_cm', 'width_cm', 'height_cm'):
            form = self.form(**{name: ''})
            self.assertFalse(form.is_valid(), name)
            self.assertIn(name, form.errors)
        self.assertTrue(self.form().is_valid())

    def test_specs_must_be_positive_and_description_meaningful(self):
        self.assertIn('weight_kg', self.form(weight_kg='0').errors)
        self.assertIn('height_cm', self.form(height_cm='-3').errors)
        self.assertIn('description', self.form(description='ok').errors)

    def test_add_item_saves_details_and_opens_item_page(self):
        self.client.login(username='seller_d', password=PASSWORD)
        page = self.client.get(reverse('add_item'))
        for label in ('Description', 'Condition', 'Weight, kg', 'Length, cm', 'Width, cm', 'Height, cm'):
            self.assertContains(page, label)
        r = self.client.post(reverse('add_item'), {'title': 'Headphones', 'price': 12000,
                                                   'category': self.cat.id, **DETAILS})
        item = ItemListing.objects.get(title='Headphones')
        self.assertRedirects(r, reverse('item_detail', args=[item.id]))
        self.assertEqual((item.weight_kg, item.dimensions, item.condition), (Decimal('1.2'), '24 × 17 × 3', 'good'))

    def test_item_page_shows_specs_and_buy_button(self):
        item = self.form(price=9000).save(commit=False)
        item.seller = self.seller
        item.save()
        self.client.login(username='buyer_d', password=PASSWORD)
        page = self.client.get(reverse('item_detail', args=[item.id]))
        for text in ('Clean copy, no notes inside.', 'Good', '1.2 kg', '24 × 17 × 3 cm', 'Timur',
                     reverse('buy_item', args=[item.id])):
            self.assertContains(page, text)

        r = self.client.post(reverse('buy_item', args=[item.id]), {'next': reverse('profile')})
        self.assertRedirects(r, reverse('profile'), fetch_redirect_response=False)
        page = self.client.get(reverse('item_detail', args=[item.id]))
        self.assertContains(page, 'This item has already been sold.')
        self.assertNotContains(page, reverse('buy_item', args=[item.id]))

    def test_item_page_states_for_owner_and_guest(self):
        item = ItemListing.objects.create(title='Old item', price=500, seller=self.seller, category=self.cat)
        url = reverse('item_detail', args=[item.id])
        guest = self.client.get(url)
        self.assertContains(guest, 'Log in to buy')
        self.assertContains(guest, 'The seller has not added a description.')   # старое объявление без описания
        self.client.login(username='seller_d', password=PASSWORD)
        self.assertContains(self.client.get(url), 'This is your listing')
        self.assertEqual(self.client.get(reverse('item_detail', args=[99999])).status_code, 404)


class ProfileTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller_p', password=PASSWORD, phone='+77010000011',
                                               student_id='24B200001', first_name='Madina')
        self.buyer = User.objects.create_user(username='buyer_p', password=PASSWORD, phone='+77010000012',
                                              first_name='Dias')
        cat = Category.objects.create(name='Textbooks')
        self.selling = ItemListing.objects.create(title='Calculus', price=3000, seller=self.seller, category=cat)
        self.sold = ItemListing.objects.create(title='Physics', price=2000, seller=self.seller, category=cat)
        purchase_listing(self.sold.id, buyer=self.buyer)

    def test_profile_requires_login(self):
        r = self.client.get(reverse('profile'))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('profile')}", fetch_redirect_response=False)

    def test_seller_sees_phone_selling_and_sold(self):
        self.client.login(username='seller_p', password=PASSWORD)
        r = self.client.get(reverse('profile'))
        self.assertContains(r, '+7 701 000 00 11')
        self.assertContains(r, '24B200001')
        self.assertEqual(r.context['active_listings'], [self.selling])
        self.assertEqual(list(r.context['sold_listings']), [self.sold])
        self.assertContains(r, 'Dias')                                          # покупатель проданного
        self.assertContains(r, reverse('mark_as_sold', args=[self.selling.id]))

    def test_buyer_sees_purchases(self):
        self.client.login(username='buyer_p', password=PASSWORD)
        r = self.client.get(reverse('profile'))
        self.assertEqual([tx.listing for tx in r.context['purchases']], [self.sold])
        self.assertContains(r, '+7 701 000 00 12')

    def test_mark_as_sold_by_buyer_phone(self):
        self.client.login(username='seller_p', password=PASSWORD)
        self.client.post(reverse('mark_as_sold', args=[self.selling.id]), {'buyer': '8 701 000 00 12'})
        self.selling.refresh_from_db()
        self.assertEqual(self.selling.status, 'Sold')
        self.assertEqual(self.selling.transaction.buyer, self.buyer)

    def test_mark_as_sold_by_get_link_changes_nothing(self):
        self.client.login(username='seller_p', password=PASSWORD)
        self.client.get(reverse('mark_as_sold', args=[self.selling.id]), {'buyer': '+77010000012'})
        self.selling.refresh_from_db()
        self.assertEqual(self.selling.status, 'Active')


class CatalogPageTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller_c', password=PASSWORD, first_name='Aruzhan')
        self.buyer = User.objects.create_user(username='buyer_c', password=PASSWORD)
        cat = Category.objects.create(name='Textbooks')
        self.item = ItemListing.objects.create(title='Calculus', price=3000, seller=self.seller, category=cat,
                                               image_url='marketplace/img/items/textbook.svg')

    def test_main_page_is_catalog_with_hero(self):
        self.assertEqual(reverse('item_list'), '/')
        r = self.client.get('/')
        self.assertContains(r, 'class="hero"')
        self.assertContains(r, 'Calculus')

    def test_guest_sees_blurred_cards_with_login_hint(self):
        r = self.client.get(reverse('item_list'))
        self.assertContains(r, 'is-locked')
        self.assertContains(r, 'Log in to buy')

    def test_logged_in_card_links_to_item_page_and_shows_image(self):
        self.client.login(username='buyer_c', password=PASSWORD)
        r = self.client.get(reverse('item_list'))
        self.assertNotContains(r, 'is-locked')
        self.assertContains(r, reverse('item_detail', args=[self.item.id]))
        self.assertContains(r, 'marketplace/img/items/textbook.svg')
        self.assertContains(r, 'Aruzhan')                                        # имя продавца, не логин

    def test_header_shows_balance_and_single_add_button(self):
        self.client.login(username='buyer_c', password=PASSWORD)
        r = self.client.get(reverse('item_list'))
        self.assertContains(r, '10,000 ₸')
        self.assertEqual(r.content.decode().count(f'href="{reverse("add_item")}"'), 1)

    def test_admin_panel_is_not_available(self):
        self.assertEqual(self.client.get('/admin/').status_code, 404)


class ReviewTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller_r', password=PASSWORD)
        self.buyer = User.objects.create_user(username='buyer_r', password=PASSWORD)
        self.stranger = User.objects.create_user(username='stranger_r', password=PASSWORD)
        cat = Category.objects.create(name='Textbooks')
        self.item = ItemListing.objects.create(title='Calculus', price=3000, seller=self.seller, category=cat)
        purchase_listing(self.item.id, buyer=self.buyer)
        self.url = reverse('seller_reviews', args=['seller_r'])

    def test_buyer_can_leave_one_review_per_purchase(self):
        self.client.login(username='buyer_r', password=PASSWORD)
        data = {'listing': self.item.id, 'rating': 5, 'comment': 'Great!'}
        self.client.post(self.url, data)
        self.client.post(self.url, data)
        self.assertEqual(Review.objects.count(), 1)
        r = self.client.get(self.url)
        self.assertFalse(r.context['can_review'])
        self.assertContains(r, 'Great!')

    def test_non_buyer_and_seller_cannot_review(self):
        data = {'listing': self.item.id, 'rating': 1, 'comment': 'Fake'}
        for username in ('stranger_r', 'seller_r'):
            self.client.login(username=username, password=PASSWORD)
            self.client.post(self.url, data)
        self.assertFalse(Review.objects.exists())

    def test_rating_range_and_self_review(self):
        self.client.login(username='buyer_r', password=PASSWORD)
        self.client.post(self.url, {'listing': self.item.id, 'rating': 9, 'comment': 'x'})
        self.assertFalse(Review.objects.exists())
        with self.assertRaises(ValidationError):
            Review(reviewer=self.seller, seller=self.seller, rating=5, comment='me').full_clean()


class TranslationTests(TestCase):
    def test_language_switch_translates_new_pages(self):
        self.client.post(reverse('set_language'), {'language': 'ru', 'next': '/'})
        self.assertContains(self.client.get(reverse('login')), 'Получить код')
        self.client.post(reverse('set_language'), {'language': 'kk', 'next': '/'})
        self.assertContains(self.client.get(reverse('register')), 'Кодты алу')
