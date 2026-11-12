from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import User, ItemListing, Category, Transaction, Review
from .forms import StudentRegisterForm, ItemListingForm
from .services import PurchaseError, purchase_listing

def item_list(request):
    query = request.GET.get('q', '')
    items = ItemListing.objects.filter(status='Active').order_by('-created_at')

    if query:
        items = items.filter(
            Q(title__icontains=query) |
            Q(seller__username__icontains=query) |
            Q(category__name__icontains=query)
        )

    return render(request, 'marketplace/item_list.html', {'items': items, 'query': query})

@login_required
def add_item(request):
    if request.method == 'POST':
        form = ItemListingForm(request.POST)
        form.user = request.user 
        if form.is_valid():
            item = form.save(commit=False)
            item.seller = request.user
            item.save()
            return redirect('item_list')
    else:
        form = ItemListingForm()
    return render(request, 'marketplace/add_item.html', {'form': form})

@login_required
@require_POST
def buy_item(request, item_id):
    """Покупка товара текущим пользователем (покупатель = request.user)."""
    item = get_object_or_404(ItemListing, id=item_id)
    try:
        purchase_listing(item.id, buyer=request.user)
    except PurchaseError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'You have bought "{item.title}".')
    return redirect('item_list')


@login_required
def mark_as_sold(request, item_id):
    """Продавец отмечает товар проданным конкретному покупателю.

    Покупатель передаётся параметром `buyer` (username) в POST или GET.
    Продавец больше не может записать покупателем самого себя.
    """
    item = get_object_or_404(ItemListing, id=item_id, seller=request.user)

    buyer_username = (request.POST.get('buyer') or request.GET.get('buyer') or '').strip()
    if not buyer_username:
        messages.error(request, 'Specify the buyer to mark this item as sold.')
        return redirect('item_list')

    buyer = User.objects.filter(username=buyer_username, is_active=True).first()
    if buyer is None:
        messages.error(request, f'User "{buyer_username}" was not found.')
        return redirect('item_list')

    try:
        purchase_listing(item.id, buyer=buyer)
    except PurchaseError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'"{item.title}" is marked as sold to {buyer.username}.')
    return redirect('item_list')


def register_view(request):
    if request.method == 'POST':
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('item_list')
    else:
        form = StudentRegisterForm()
    return render(request, 'marketplace/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('item_list')
    else:
        form = AuthenticationForm()
    return render(request, 'marketplace/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('item_list')