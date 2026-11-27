"""Помощники для шаблонов: картинка товара, звёзды рейтинга, телефон."""
from django import template
from django.templatetags.static import static

from ..phone_auth import format_phone
from .marketplace_extras import category_image

register = template.Library()


@register.simple_tag
def item_image(item):
    """URL картинки товара: своя картинка, иначе картинка категории."""
    url = (item.image_url or '').strip()
    if url.startswith(('http://', 'https://', '/')):
        return url
    if url:
        return static(url)
    return category_image(item.category.name)


@register.filter
def stars(rating):
    """4 -> '★★★★☆' (для средних значений округляет)."""
    try:
        n = int(round(float(rating)))
    except (TypeError, ValueError):
        return ''
    n = max(0, min(5, n))
    return '★' * n + '☆' * (5 - n)


@register.filter
def phone(value):
    """+77011234567 -> +7 701 123 45 67"""
    return format_phone(value)
