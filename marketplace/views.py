from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import ItemListing, Category, Transaction, Review
from .forms import StudentRegisterForm, ItemListingForm

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
def mark_as_sold(request, item_id):
    item = get_object_or_404(ItemListing, id=item_id, seller=request.user)
    item.status = 'Sold'
    item.save()
    
    Transaction.objects.create(listing=item, buyer=request.user)
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