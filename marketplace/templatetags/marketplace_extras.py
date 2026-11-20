from django import template
from django.templatetags.static import static

register = template.Library()

# Ключевые слова (EN + RU) -> имя локального SVG в static/marketplace/img/categories/.
# Порядок важен: берётся первое совпадение.
CATEGORY_IMAGES = (
    ('books', ('book', 'textbook', 'литер', 'книг', 'учеб')),
    ('electronics', ('electr', 'laptop', 'phone', 'gadget', 'comput',
                     'электрон', 'ноутбук', 'телефон', 'гаджет', 'компьют')),
    ('furniture', ('furnit', 'home', 'dorm', 'мебел', 'дом', 'общаг')),
    ('clothing', ('cloth', 'apparel', 'fashion', 'shoe', 'одежд', 'обув')),
    ('sports', ('sport', 'fitness', 'спорт')),
    ('stationery', ('stationer', 'supplies', 'office', 'канц')),
)


@register.simple_tag
def category_image(category_name):
    """URL локальной картинки-заглушки для категории (или универсальной)."""
    name = (category_name or '').lower()
    key = 'default'
    for image_key, keywords in CATEGORY_IMAGES:
        if any(word in name for word in keywords):
            key = image_key
            break
    return static(f'marketplace/img/categories/{key}.svg')
