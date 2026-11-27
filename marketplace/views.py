import secrets

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import phone_auth
from .filters import ItemFilterForm
from .forms import (CodeForm, ItemListingForm, PhoneLoginForm, PhoneRegisterForm, ReviewForm,
                    WalletForm)
from .models import Category, ItemListing, Review, User
from .services import (PurchaseError, ReviewError, WalletError, deposit, leave_review,
                       purchase_listing, reviewable_purchases, withdraw)


def _safe_next(request, default='item_list'):
    """Куда вернуться после действия: ?next=... (только наш сайт) или default."""
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return reverse(default) if not default.startswith('/') else default


def _active_items():
    return (ItemListing.objects.filter(status='Active')
            .select_related('seller', 'category'))


# ---------------------------------------------------------------------------
# Каталог (главная) и страница товара
# ---------------------------------------------------------------------------

def item_list(request):
    filters = ItemFilterForm(request.GET).cleaned_or_empty()
    query = filters['q']
    category = filters['category']
    min_price = filters['min_price']
    max_price = filters['max_price']

    items = _active_items().order_by('-created_at')

    if query:
        items = items.filter(
            Q(title__icontains=query) |
            Q(seller__username__icontains=query) |
            Q(seller__first_name__icontains=query) |
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


def item_detail(request, item_id):
    """Страница товара: описание, характеристики, продавец и кнопка покупки."""
    item = get_object_or_404(ItemListing.objects.select_related('seller', 'category'), id=item_id)
    seller_rating = item.seller.reviews_received.aggregate(avg=Avg('rating'), n=Count('id'))
    more_items = (_active_items().filter(seller=item.seller).exclude(id=item.id)
                  .order_by('-created_at')[:3])
    return render(request, 'marketplace/item_detail.html', {
        'item': item,
        'seller_rating': seller_rating,
        'more_items': more_items,
    })


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
            return redirect('item_detail', item_id=item.id)
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


def _find_buyer(value):
    """Покупатель по номеру телефона (основной способ) или по логину."""
    value = (value or '').strip()
    phone = phone_auth.normalize_phone(value)
    users = User.objects.filter(is_active=True)
    if phone:
        return users.filter(phone=phone).first()
    return users.filter(username=value).first()


@login_required
def mark_as_sold(request, item_id):
    """Продавец отмечает товар проданным конкретному покупателю (сделка при встрече).

    Покупатель передаётся только POST-параметром `buyer` (номер телефона или логин):
    обычный переход по ссылке (GET) ничего не меняет в базе.
    """
    item = get_object_or_404(ItemListing, id=item_id, seller=request.user)
    if request.method != 'POST':
        return redirect('item_list')

    buyer_value = (request.POST.get('buyer') or '').strip()
    if not buyer_value:
        messages.error(request, _('Specify the buyer to mark this item as sold.'))
        return redirect(_safe_next(request))

    buyer = _find_buyer(buyer_value)
    if buyer is None:
        messages.error(request, _('User "%(name)s" was not found.') % {'name': buyer_value})
        return redirect(_safe_next(request))

    try:
        # Сделка прошла при встрече (оплата наличными) — баланс не списываем.
        purchase_listing(item.id, buyer=buyer, charge=False)
    except PurchaseError as exc:
        messages.error(request, _(str(exc)))
    else:
        messages.success(request, _('"%(title)s" is marked as sold to %(name)s.')
                         % {'title': item.title, 'name': buyer.display_name})
    return redirect(_safe_next(request))


# ---------------------------------------------------------------------------
# Профиль, баланс и отзывы
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
        'phone_display': phone_auth.format_phone(user.phone),
        'active_listings': [i for i in listings if i.status == 'Active'],
        'sold_listings': (listings.filter(status='Sold')
                          .select_related('transaction__buyer')),
        'purchases': purchases,
        'reviewed_ids': reviewed_ids,
        'rating': rating,
        'operations': user.wallet_operations.select_related('listing')[:20],
        'deposit_form': WalletForm(prefix='deposit'),
        'withdraw_form': WalletForm(prefix='withdraw'),
    })


@login_required
@require_POST
def wallet_operation(request, kind):
    """Пополнение (kind='deposit') или вывод (kind='withdraw') баланса."""
    if kind not in ('deposit', 'withdraw'):
        return redirect('profile')
    form = WalletForm(request.POST, prefix=kind)
    if not form.is_valid():
        messages.error(request, _('The amount must be between 100 and 500,000 KZT.'))
        return redirect(reverse('profile') + '#wallet')
    amount = form.cleaned_data['amount']
    try:
        if kind == 'deposit':
            deposit(request.user, amount)
            messages.success(request, _('Balance topped up by %(amount)s ₸.') % {'amount': f'{amount:,.0f}'})
        else:
            withdraw(request.user, amount)
            messages.success(request, _('%(amount)s ₸ withdrawn from your balance.') % {'amount': f'{amount:,.0f}'})
    except WalletError as exc:
        messages.error(request, _(str(exc)))
    return redirect(reverse('profile') + '#wallet')


def seller_reviews(request, username):
    """Страница отзывов о продавце + форма отзыва после покупки."""
    seller = get_object_or_404(User, username=username)
    purchases = list(reviewable_purchases(request.user, seller))

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
        form = ReviewForm(request.POST, purchases=purchases)
        if form.is_valid():
            try:
                leave_review(request.user, seller, form.cleaned_data['listing'],
                             form.cleaned_data['rating'], form.cleaned_data['comment'])
            except ReviewError as exc:
                messages.error(request, _(str(exc)))
            else:
                messages.success(request, _('Your review is published.'))
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
        'active_items': _active_items().filter(seller=seller).order_by('-created_at')[:3],
    })


# ---------------------------------------------------------------------------
# Аккаунт: регистрация и вход по номеру телефона
# ---------------------------------------------------------------------------

def _new_username():
    """Внутренний логин (в URL отзывов). Номер телефона в адресах не показываем."""
    while True:
        username = 'u' + secrets.token_hex(4)
        if not User.objects.filter(username=username).exists():
            return username


def register_view(request):
    if request.user.is_authenticated:
        return redirect('item_list')
    if request.method == 'POST':
        form = PhoneRegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            phone_auth.start_verification(request, data['phone'], 'register', {
                'first_name': data['first_name'], 'student_id': data['student_id'],
            })
            return redirect('verify_phone')
    else:
        form = PhoneRegisterForm()
    return render(request, 'marketplace/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('item_list')
    if request.method == 'POST':
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone_auth.start_verification(request, form.cleaned_data['phone'], 'login',
                                          {'next': _safe_next(request)})
            return redirect('verify_phone')
    else:
        form = PhoneLoginForm()
    return render(request, 'marketplace/login.html', {'form': form, 'next': request.GET.get('next', '')})


def verify_phone(request):
    """Второй шаг входа и регистрации: ввод кода из SMS."""
    pending = phone_auth.pending(request)
    if not pending:
        return redirect('login')

    if request.method == 'POST' and 'resend' in request.POST:
        if phone_auth.can_resend(request):
            phone_auth.resend(request)
            messages.info(request, _('A new code has been sent.'))
        else:
            messages.warning(request, _('Wait 30 seconds before requesting a new code.'))
        return redirect('verify_phone')

    form = CodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            data = phone_auth.check_code(request, form.cleaned_data['code'])
        except phone_auth.VerificationError as exc:
            form.add_error('code', _(str(exc)))
            if not phone_auth.pending(request):
                messages.error(request, _(str(exc)))
                return redirect('register' if pending['purpose'] == 'register' else 'login')
        else:
            if data['purpose'] == 'register':
                payload = data['payload']
                if User.objects.filter(phone=data['phone']).exists():
                    messages.error(request, _('This phone number is already registered.'))
                    return redirect('login')
                user = User(username=_new_username(), phone=data['phone'],
                            first_name=payload['first_name'], student_id=payload['student_id'])
                user.set_unusable_password()
                user.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, _('Welcome, %(name)s! You have 10,000 ₸ on your balance.')
                                 % {'name': user.display_name})
                return redirect('item_list')
            user = User.objects.filter(phone=data['phone'], is_active=True).first()
            if user is None:
                messages.error(request, _('No account with this phone number. Register first.'))
                return redirect('register')
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect(data['payload'].get('next') or reverse('item_list'))

    return render(request, 'marketplace/verify_phone.html', {
        'form': form,
        'phone_display': phone_auth.format_phone(pending['phone']),
        'purpose': pending['purpose'],
        'demo_code': pending.get('demo_code'),
    })


def logout_view(request):
    logout(request)
    return redirect('item_list')
