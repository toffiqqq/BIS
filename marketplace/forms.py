from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User, ItemListing, Category, Review


class StudentRegisterForm(UserCreationForm):
    student_id = forms.CharField(max_length=20, required=False, label=_("Student ID"))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'student_id')


class ItemListingForm(forms.ModelForm):
    class Meta:
        model = ItemListing
        fields = ('title', 'price', 'category', 'image_url')
        labels = {
            'title': _('Title'),
            'price': _('Price (KZT)'),
            'category': _('Category'),
            'image_url': _('Image link (optional)'),
        }
        help_texts = {
            'image_url': _('Leave empty to use the category picture.'),
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None or price <= 0:
            raise forms.ValidationError(_("Item price must be greater than 0 KZT."))
        if price > 100000:
            raise forms.ValidationError(_("Item price exceeds the maximum limit (100,000 KZT)."))
        return price

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self, 'user', None)
        if user:
            active_ads_count = ItemListing.objects.filter(seller=user, status='Active').count()
            if active_ads_count >= 10:
                raise forms.ValidationError(_("Limit exceeded: a student cannot have more than 10 active listings at the same time."))
        return cleaned_data


SORT_CHOICES = [
    ('new', _('Newest first')),
    ('cheap', _('Price: low to high')),
    ('expensive', _('Price: high to low')),
]


class CatalogFilterForm(forms.Form):
    """Поиск + фильтры каталога. Все поля необязательные (GET-параметры)."""
    q = forms.CharField(required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.order_by('name'), required=False)
    min_price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False)


class ReviewForm(forms.Form):
    listing = forms.TypedChoiceField(coerce=int, label=_('Purchase'))
    rating = forms.TypedChoiceField(
        coerce=int, label=_('Rating'),
        choices=[(i, '★' * i) for i in range(5, 0, -1)])
    comment = forms.CharField(
        label=_('Comment'), max_length=1000,
        widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, purchases=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing'].choices = [
            (tx.listing_id, f'{tx.listing.title} — {tx.listing.price:.0f} ₸') for tx in purchases
        ]
