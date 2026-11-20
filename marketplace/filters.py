from decimal import Decimal

from django import forms

from .models import Category


# Верхняя граница = максимум поля price (max_digits=10, decimal_places=2).
MAX_PRICE = Decimal('99999999.99')


class ItemFilterForm(forms.Form):
    """GET-фильтры каталога: поиск, категория, диапазон цены.

    Все поля необязательные. Некорректные значения (например, текст вместо
    числа) не ломают страницу — форма просто считает их пустыми.
    """
    q = forms.CharField(required=False)
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(), required=False, empty_label=None,
    )
    min_price = forms.DecimalField(required=False, min_value=0, max_value=MAX_PRICE, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=0, max_value=MAX_PRICE, decimal_places=2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.order_by('name')

    def cleaned_or_empty(self):
        """Возвращает чистые значения; невалидные поля заменяются пустыми."""
        self.is_valid()
        data = {name: self.cleaned_data.get(name) for name in self.fields}
        data['q'] = (data['q'] or '').strip()
        low, high = data['min_price'], data['max_price']
        if low is not None and high is not None and low > high:
            data['min_price'], data['max_price'] = high, low
        return data
