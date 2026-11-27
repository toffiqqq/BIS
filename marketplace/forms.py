from django import forms
from django.utils.translation import gettext_lazy as _

from .models import User, ItemListing
from .phone_auth import normalize_phone
from .services import WALLET_MAX, WALLET_MIN


class PhoneField(forms.CharField):
    """Поле номера телефона: принимает любой привычный формат, хранит +7XXXXXXXXXX."""
    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Phone number'))
        kwargs.setdefault('max_length', 20)
        super().__init__(**kwargs)
        self.widget.attrs.update({'placeholder': '+7 701 123 45 67', 'inputmode': 'tel',
                                  'autocomplete': 'tel'})

    def clean(self, value):
        value = super().clean(value)
        phone = normalize_phone(value)
        if not phone:
            raise forms.ValidationError(_('Enter a phone number like +7 701 123 45 67.'))
        return phone


class PhoneLoginForm(forms.Form):
    phone = PhoneField()

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not User.objects.filter(phone=phone, is_active=True).exists():
            raise forms.ValidationError(_('No account with this phone number. Register first.'))
        return phone


class PhoneRegisterForm(forms.Form):
    phone = PhoneField()
    first_name = forms.CharField(label=_('Your name'), max_length=150)
    student_id = forms.CharField(max_length=20, required=False, label=_('Student ID'))

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError(_('This phone number is already registered.'))
        return phone

    def clean_student_id(self):
        student_id = (self.cleaned_data.get('student_id') or '').strip()
        if student_id and User.objects.filter(student_id=student_id).exists():
            raise forms.ValidationError(_('User with this Student ID already exists.'))
        return student_id or None


class CodeForm(forms.Form):
    code = forms.CharField(label=_('Code'), min_length=4, max_length=4,
                           widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code',
                                                         'pattern': '[0-9]*', 'autofocus': True}))


class WalletForm(forms.Form):
    amount = forms.DecimalField(label=_('Amount, KZT'), min_value=WALLET_MIN, max_value=WALLET_MAX,
                                decimal_places=2, widget=forms.NumberInput(attrs={'step': '100'}))


class ItemListingForm(forms.ModelForm):
    class Meta:
        model = ItemListing
        fields = ('title', 'price', 'category', 'description', 'condition',
                  'weight_kg', 'length_cm', 'width_cm', 'height_cm', 'image_url')
        labels = {
            'title': _('Title'),
            'price': _('Price (KZT)'),
            'category': _('Category'),
            'description': _('Description'),
            'condition': _('Condition'),
            'weight_kg': _('Weight, kg'),
            'length_cm': _('Length, cm'),
            'width_cm': _('Width, cm'),
            'height_cm': _('Height, cm'),
            'image_url': _('Image link (optional)'),
        }
        help_texts = {
            'description': _('Condition, defects, what comes with it.'),
            'image_url': _('Leave empty to use the category picture.'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'weight_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'length_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.1'}),
            'width_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.1'}),
            'height_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.1'}),
        }

    # Описание и характеристики — обязательные поля.
    REQUIRED_DETAILS = ('description', 'weight_kg', 'length_cm', 'width_cm', 'height_cm')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.REQUIRED_DETAILS:
            self.fields[name].required = True
        self.fields['category'].empty_label = '—'

    def clean_description(self):
        text = (self.cleaned_data.get('description') or '').strip()
        if len(text) < 10:
            raise forms.ValidationError(_('Describe the item in more detail, at least 10 characters.'))
        return text

    def _positive(self, name):
        value = self.cleaned_data.get(name)
        if value is not None and value <= 0:
            raise forms.ValidationError(_('Must be greater than 0.'))
        return value

    def clean_weight_kg(self):
        return self._positive('weight_kg')

    def clean_length_cm(self):
        return self._positive('length_cm')

    def clean_width_cm(self):
        return self._positive('width_cm')

    def clean_height_cm(self):
        return self._positive('height_cm')

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None or price <= 0:
            raise forms.ValidationError(_("Item price must be greater than 0 KZT."))
        if price > 100000:
            raise forms.ValidationError(_("The price can't be higher than 100,000 KZT."))
        return price

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self, 'user', None)
        if user:
            active_ads_count = ItemListing.objects.filter(seller=user, status='Active').count()
            if active_ads_count >= 10:
                raise forms.ValidationError(_("You already have 10 active listings. Sell one before posting a new one."))
        return cleaned_data


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
