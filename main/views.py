from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from borrow.models import Librarian, Patron, BorrowedItem, BorrowRequest, CollectionRequest 
from allauth.socialaccount.models import SocialAccount


from django.shortcuts import render, redirect

def home(request):
    # — Public landing when NOT signed in —
    if not request.user.is_authenticated:
        return render(request, "home.html", {
            "public": True,
        })

    # — Must be a Patron to see dashboard —
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        patron = Patron.objects.create(
            user=request.user,
            email=request.user.email,
            name=request.user.get_full_name(),
        )

    # grab their borrowed items
    borrowed_items = BorrowedItem.objects.filter(borrower=patron, returned=False)
    now = timezone.now()
    due_soon = [b for b in borrowed_items if 0 <= (b.due_date - now).days <= 1]
    overdue  = [b for b in borrowed_items if b.is_late()]

    context = {
        "public":         False,
        "borrowed_items": borrowed_items,
        "due_soon":       due_soon,
        "overdue":        overdue,
        "is_librarian":   False,
    }

    # if they’re a librarian, show pending requests
    if Librarian.objects.filter(user=request.user).exists():
        context["is_librarian"]       = True
        context["borrow_requests"]    = BorrowRequest.objects.filter(status=BorrowRequest.PENDING)
        context["collection_requests"]= CollectionRequest.objects.filter(status=CollectionRequest.PENDING)

    return render(request, "home.html", context)

@login_required
def profile_view(request):
    # Check if user is a superuser first
    is_superuser = request.user.is_superuser
    
    # Try to get the existing Patron instance
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        # Only create a new one if it doesn't exist and is not a superuser
        if not is_superuser:
            patron = Patron.objects.create(
                user=request.user,
                email=request.user.email,
                name=request.user.get_full_name(),
            )
        else:
            # For superusers without patron accounts, create a minimal context
            return render(request, 'account/profile.html', {
                'role': 'superuser',
                'patron': None
            })
    
    # Check if the user has a Librarian instance
    librarian = Librarian.objects.filter(user=request.user).first()
    
    # Determine user role: superuser > librarian > patron > unknown
    if is_superuser:
        role = "superuser"
    elif librarian:
        role = "librarian"
    elif patron:
        role = "patron"
    else:
        role = "unknown"
    
    # Handle profile photo upload
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        if patron:  # Only try to update if patron exists
            patron.profile_photo = request.FILES['profile_photo']
            patron.save()
        return redirect('profile')
    
    return render(request, 'account/profile.html', {'role': role, 'patron': patron})

    
def redirect_to_home(request):
    """Redirect users trying to access AllAuth pages to the home page with a message"""
    messages.info(request, "Please use Google login to sign in or register.", extra_tags='current-page')
    return HttpResponseRedirect(reverse('home'))
