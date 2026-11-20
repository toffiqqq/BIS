from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import CatalogFilterForm, ItemListingForm, ReviewForm, StudentRegisterForm
from .models import Category, ItemListing, Review, Transaction, User
from .services import (PurchaseError, ReviewError, leave_review, purchase_listing,
                       reviewable_purchases)

# Категории, которые показываются плитками на главной странице.
HOME_CATEGORIES = ['Textbooks', 'Electronics', 'Stationery', 'Household']
BUDGET_LIMIT = 5000  # «бюджетные» предложения — до 5 000 ₸


def _safe_next(request, default='item_list'):
    """Куда вернуться после действия: ?next=... (только наш сайт) или default."""
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return default


def _active_items():
    return (ItemListing.objects.filter(status='Active')
            .select_related('seller', 'category'))


# ---------------------------------------------------------------------------
# Главная-витрина и каталог
# ---------------------------------------------------------------------------

def home(request):
    categories = {c.name: c for c in Category.objects.filter(name__in=HOME_CATEGORIES)
                  .annotate(active_count=Count('items', filter=Q(items__status='Active')))}
    tiles = [categories[name] for name in HOME_CATEGORIES if name in categories]

    active = _active_items()
    context = {
        'tiles': tiles,
        'fresh_items': active.order_by('-created_at')[:4],
        'budget_items': active.filter(price__lte=BUDGET_LIMIT).order_by('price', '-created_at')[:4],
        'budget_limit': BUDGET_LIMIT,
    }
    return render(request, 'marketplace/home.html', context)


def item_list(request):
    """Каталог: поиск + фильтр по категории и цене + сортировка + страницы."""
    form = CatalogFilterForm(request.GET or None)
    items = _active_items()
    query = ''
    order = '-created_at'

    if form.is_valid():
        data = form.cleaned_data
        query = (data.get('q') or '').strip()
        if query:
            items = items.filter(
                Q(title__icontains=query) |
                Q(seller__username__icontains=query) |
                Q(category__name__icontains=query)
            )
        if data.get('category'):
            items = items.filter(category=data['category'])
        if data.get('min_price') is not None:
            items = items.filter(price__gte=data['min_price'])
        if data.get('max_price') is not None:
            items = items.filter(price__lte=data['max_price'])
        order = {'cheap': 'price', 'expensive': '-price'}.get(data.get('sort'), '-created_at')
    elif request.GET:
        messages.warning(request, _('Some filter values were invalid and were ignored.'))

    items = items.order_by(order, '-id')
    page = Paginator(items, 12).get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)
    has_filters = any(v for k, v in request.GET.items() if k not in ('page', 'sort'))

    return render(request, 'marketplace/item_list.html', {
        'items': page.object_list,
        'page_obj': page,
        'query': query,
        'filter_form': form if form.is_bound else CatalogFilterForm(),
        'categories': Category.objects.order_by('name'),
        'querystring': params.urlencode(),
        'has_filters': has_filters,
        'total': page.paginator.count,
    })

from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from .models import User, ItemListing, Category, Transaction, Review
from .forms import StudentRegisterForm, ItemListingForm
from .filters import ItemFilterForm
from .services import PurchaseError, purchase_listing

def item_list(request):
    filters = ItemFilterForm(request.GET).cleaned_or_empty()
    query = filters['q']
    category = filters['category']
    min_price = filters['min_price']
    max_price = filters['max_price']

    items = (
        ItemListing.objects.filter(status='Active')
        .select_related('category', 'seller')
        .order_by('-created_at')
    )

    if query:
        items = items.filter(
            Q(title__icontains=query) |
            Q(seller__username__icontains=query) |
            Q(category__name__icontains=query)
        )
    if category:
        items = items.filter(category=category)
    if min_price is not None:
        items = items.filter(price__gte=min_price)
    if max_price is not None:
        items = items.filter(price__lte=max_price)

    categories = Category.objects.annotate(
        active_count=Count('items', filter=Q(items__status='Active'))
    ).order_by('name')

    has_filters = bool(query or category or min_price is not None or max_price is not None)
    context = {
        'items': items,
        'query': query,
        'categories': categories,
        # Плитки в hero-баннере: 4 самые «живые» категории.
        'hero_categories': sorted(categories, key=lambda c: (-c.active_count, c.name))[:4],
        'selected_category': category.pk if category else None,
        'min_price': min_price if min_price is not None else '',
        'max_price': max_price if max_price is not None else '',
        'has_filters': has_filters,
    }
    return render(request, 'marketplace/item_list.html', context)

@login_required
def add_item(request):
    if request.method == 'POST':
        form = ItemListingForm(request.POST)
        form.user = request.user
        if form.is_valid():
            item = form.save(commit=False)
            item.seller = request.user
            item.save()
            messages.success(request, _('Your listing "%(title)s" is now live.') % {'title': item.title})
            return redirect('item_list')
    else:
        form = ItemListingForm()
    return render(request, 'marketplace/add_item.html', {'form': form})


# ---------------------------------------------------------------------------
# Покупка
# ---------------------------------------------------------------------------

@login_required
@require_POST
def buy_item(request, item_id):
    """Покупка товара текущим пользователем (покупатель = request.user)."""
    item = get_object_or_404(ItemListing, id=item_id)
    try:
        purchase_listing(item.id, buyer=request.user)
    except PurchaseError as exc:
        messages.error(request, _(str(exc)))
    else:
        messages.success(request, _('You have bought "%(title)s".') % {'title': item.title})
    return redirect(_safe_next(request))


@login_required
def mark_as_sold(request, item_id):
    """Продавец отмечает товар проданным конкретному покупателю.

    Покупатель передаётся только POST-параметром `buyer` (username):
    обычный переход по ссылке (GET) ничего не меняет в базе.
    """
    item = get_object_or_404(ItemListing, id=item_id, seller=request.user)
    if request.method != 'POST':
        return redirect('item_list')

    buyer_username = (request.POST.get('buyer') or '').strip()
    if not buyer_username:
        messages.error(request, _('Specify the buyer to mark this item as sold.'))
        return redirect(_safe_next(request))

    buyer = User.objects.filter(username=buyer_username, is_active=True).first()
    if buyer is None:
        messages.error(request, _('User "%(name)s" was not found.') % {'name': buyer_username})
        return redirect(_safe_next(request))

    try:
        # Сделка прошла при встрече (оплата наличными) — баланс не списываем.
        purchase_listing(item.id, buyer=buyer, charge=False)
    except PurchaseError as exc:
        messages.error(request, _(str(exc)))
    else:
        messages.success(request, _('"%(title)s" is marked as sold to %(name)s.')
                         % {'title': item.title, 'name': buyer.username})
    return redirect(_safe_next(request))


# ---------------------------------------------------------------------------
# Профиль и отзывы
# ---------------------------------------------------------------------------

@login_required
def profile(request):
    user = request.user
    listings = user.listings.select_related('category').order_by('-created_at')
    purchases = (user.purchases.select_related('listing__seller', 'listing__category')
                 .order_by('-completed_at'))
    reviewed_ids = set(Review.objects.filter(reviewer=user, listing__isnull=False)
                       .values_list('listing_id', flat=True))
    rating = user.reviews_received.aggregate(avg=Avg('rating'), n=Count('id'))

    return render(request, 'marketplace/profile.html', {
        'profile_user': user,
        'active_listings': [i for i in listings if i.status == 'Active'],
        'sold_listings': (listings.filter(status='Sold')
                          .select_related('transaction__buyer')),
        'purchases': purchases,
        'reviewed_ids': reviewed_ids,
        'rating': rating,
        'total_spent': sum(tx.listing.price for tx in purchases),
    })


def seller_reviews(request, username):
    """Страница отзывов о продавце + форма отзыва после покупки."""
    seller = get_object_or_404(User, username=username)
    purchases = list(reviewable_purchases(request.user, seller))

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{_login_url()}?next={request.path}")
        form = ReviewForm(request.POST, purchases=purchases)
        if form.is_valid():
            try:
                leave_review(request.user, seller, form.cleaned_data['listing'],
                             form.cleaned_data['rating'], form.cleaned_data['comment'])
            except ReviewError as exc:
                messages.error(request, _(str(exc)))
            else:
                messages.success(request, _('Thank you! Your review has been published.'))
            return redirect('seller_reviews', username=seller.username)
    else:
        initial = {}
        if request.GET.get('listing', '').isdigit():
            initial['listing'] = int(request.GET['listing'])
        form = ReviewForm(purchases=purchases, initial=initial)

    reviews = seller.reviews_received.select_related('reviewer', 'listing')
    summary = reviews.aggregate(avg=Avg('rating'), n=Count('id'))
    distribution = [
        {'stars': s, 'count': reviews.filter(rating=s).count()} for s in range(5, 0, -1)
    ]
    for row in distribution:
        row['percent'] = round(100 * row['count'] / summary['n']) if summary['n'] else 0

    return render(request, 'marketplace/review.html', {
        'seller': seller,
        'reviews': reviews,
        'summary': summary,
        'distribution': distribution,
        'form': form,
        'can_review': bool(purchases),
        'active_items': _active_items().filter(seller=seller).order_by('-created_at')[:4],
    })


def _login_url():
    from django.urls import reverse
    return reverse('login')


# ---------------------------------------------------------------------------
# Аккаунт
# ---------------------------------------------------------------------------

def register_view(request):
    if request.method == 'POST':
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _('Welcome to Student Marketplace, %(name)s!') % {'name': user.username})
            return redirect('home')
    else:
        form = StudentRegisterForm()
    return render(request, 'marketplace/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(_safe_next(request, default='home'))
    else:
        form = AuthenticationForm()
    return render(request, 'marketplace/login.html', {'form': form, 'next': request.GET.get('next', '')})


def logout_view(request):
    logout(request)
    return redirect('home')
