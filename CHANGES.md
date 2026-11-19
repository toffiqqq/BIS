# Изменения

## Не изменилось
- Модели `Category`, `ItemListing`, `Transaction`, `Review` и связи между ними (FK, 1:1, `PROTECT` / `RESTRICT`).
- Миграции `0001`, `0002`, команда `check_transactions`.
- Старые тесты: не изменены, проходят.
- Имена маршрутов: `item_list`, `add_item`, `buy_item`, `mark_as_sold`, `login`, `register`, `logout`.

## Добавлено
| Что | Где |
|---|---|
| Главная `/`, каталог на `/catalog/` | `views.home`, `urls.py`, `home.html` |
| Фильтры по категории и цене, сортировка, страницы | `views.item_list`, `forms.CatalogFilterForm` |
| Картинки товаров (SVG в `static/`, поле `image_url`) | `models.ItemListing.image_url`, миграция `0003`, `templatetags/market_extras.py` |
| Кнопка «Купить» в карточке | `_item_card.html` |
| Баланс 10 000 ₸, списание при покупке | `models.User.balance`, миграция `0004`, `services.purchase_listing` |
| Профиль | `views.profile`, `profile.html` |
| Отзывы | `views.seller_reviews`, `services.leave_review`, `review.html`, ограничение в `Review` |
| Размытые карточки для гостей | `_item_card.html`, `style.css` |
| Свой CSS вместо Bootstrap CDN | `static/marketplace/css/style.css` |
| Переводы RU / KK | `locale/`, `settings.LANGUAGES` |
| Стартовые данные | `management/commands/seed_demo.py` |
| Запуск на сервере | `start.sh`, `Dockerfile`, `docker-compose.yml` |

## Убрано
- Админ-панель Django (`/admin/`): приложение `django.contrib.admin`, файл `marketplace/admin.py`, маршрут в `config/urls.py`. Тест TC10 теперь проверяет, что `/admin/` отдаёт 404; тест про страницы админки удалён.

## Изменено в поведении
- `mark_as_sold` принимает покупателя только из POST-формы (раньше база менялась по GET-ссылке). Форма теперь в профиле продавца. Такая продажа считается оплаченной при встрече, баланс не списывается.
- `@login_required` ведёт на `/login/` (`LOGIN_URL`); раньше вёл на несуществующий `/accounts/login/`.
- `settings.py`: whitenoise для статики, настройки для HTTPS-хостинга, запасной режим `DJANGO_DB=sqlite`.

## После обновления
```bash
pip install -r requirements.txt
python manage.py migrate
```
