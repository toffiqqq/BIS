"""Небольшие помощники для шаблонов: картинка товара, звёзды рейтинга."""
from django import template
from django.templatetags.static import static
from django.utils.text import slugify

register = template.Library()

# Заглушки лежат в marketplace/static/marketplace/img/categories/<slug>.svg
CATEGORY_IMAGES = {'textbooks', 'electronics', 'stationery', 'household'}


@register.simple_tag
def category_image(category):
    slug = slugify(getattr(category, 'name', '') or '')
    if slug not in CATEGORY_IMAGES:
        slug = 'default'
    return static(f'marketplace/img/categories/{slug}.svg')


@register.simple_tag
def item_image(item):
    """URL картинки товара: своя картинка, иначе заглушка категории."""
    url = (item.image_url or '').strip()
    if url.startswith(('http://', 'https://', '/')):
        return url
    if url:
        return static(url)
    return category_image(item.category)


@register.filter
def stars(rating):
    """4 -> '★★★★☆' (для средних значений округляет)."""
    try:
        n = int(round(float(rating)))
    except (TypeError, ValueError):
        return ''
    n = max(0, min(5, n))
    return '★' * n + '☆' * (5 - n)
