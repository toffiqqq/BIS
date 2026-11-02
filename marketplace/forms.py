from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, ItemListing

class StudentRegisterForm(UserCreationForm):
    student_id = forms.CharField(max_length=20, required=False, label="Student ID")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'student_id')

class ItemListingForm(forms.ModelForm):
    class Meta:
        model = ItemListing
        fields = ('title', 'price', 'category')

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None or price <= 0:
            raise forms.ValidationError("Цена товара должна быть больше 0 KZT.")
        if price > 100000:
            raise forms.ValidationError("Превышен максимальный лимит стоимости товара (100,000 KZT).")
        return price

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self, 'user', None)
        if user:
            active_ads_count = ItemListing.objects.filter(seller=user, status='Active').count()
            if active_ads_count >= 10:
                raise forms.ValidationError("Превышен лимит: студент не может иметь более 10 активных объявлений одновременно.")
        return cleaned_data