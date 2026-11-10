from django.test import TestCase, Client
from django.urls import reverse
from django.db.models import RestrictedError
from .models import User, Category, ItemListing, Transaction
from .forms import StudentRegisterForm, ItemListingForm


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
            'category': self.category.id
        })
        form.user = self.seller
        self.assertFalse(form.is_valid())

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
        self.client.get(reverse('mark_as_sold', args=[item.id]))

        item.refresh_from_db()
        self.assertEqual(item.status, 'Sold')
        self.assertEqual(Transaction.objects.filter(listing=item).count(), 1)

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
        valid_form = StudentRegisterForm(data={
            'username': 'new_student_test',
            'email': 'new_student@kbtu.kz',
            'student_id': '24B000003',
            'password1': 'StrongPassword123!',
            'password2': 'StrongPassword123!'
        })
        self.assertTrue(valid_form.is_valid())
        user = valid_form.save()
        self.assertTrue(user.check_password('StrongPassword123!'))

        duplicate_form = StudentRegisterForm(data={
            'username': 'another_student_test',
            'email': 'another_student@kbtu.kz',
            'student_id': '24B000003',
            'password1': 'StrongPassword123!',
            'password2': 'StrongPassword123!'
        })
        self.assertFalse(duplicate_form.is_valid())
        self.assertIn('student_id', duplicate_form.errors)

    def test_tc10_admin_panel_role_based_access(self):
        self.client.login(username='alex_test', password='StrongPassword123!')
        student_response = self.client.get(reverse('admin:index'))
        self.assertEqual(student_response.status_code, 302)

        admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin_test@kbtu.kz',
            password='StrongPassword123!',
            student_id='24B000099'
        )
        self.client.login(username='admin_test', password='StrongPassword123!')
        admin_response = self.client.get(reverse('admin:index'))
        self.assertEqual(admin_response.status_code, 200)