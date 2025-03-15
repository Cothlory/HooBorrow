from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from borrow.models import Librarian, Patron 
from allauth.socialaccount.models import SocialAccount


def home(request):
    return render(request, "home.html")

@login_required
def profile_view(request):
    role = "unknown"
    
    # Check if the user has a related Librarian instance
    try:
        librarian = Librarian.objects.get(user=request.user)
        role = "librarian"
    except Librarian.DoesNotExist:
        librarian = None

    # Check if the user has a related Patron instance
    try:
        patron = Patron.objects.get(user=request.user)
        role = "patron"
    except Patron.DoesNotExist:
        patron = None

    if librarian and patron:
        role = "librarian" 
        
     # Handle POST request to upload profile photo
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        # Ensure that the user has a Patron instance
        if patron:
            photo = request.FILES['profile_photo']
            patron.profile_photo = photo
            patron.save()
            return redirect('profile')  # Redirect to avoid re-posting the form on refresh

    # Pass the role to the template
    return render(request, 'account/profile.html', {'role': role})

@login_required
def role_select(request):

    # Check if the user has already selected a role
    if hasattr(request.user, 'librarian') or hasattr(request.user, 'patron'):
        return redirect('home')  # If they already have a role, redirect to home
    
    if request.method == 'POST':
        role = request.POST.get('role')
        email = request.user.email
        name = request.user.get_full_name() 

        if role == 'librarian':
            Librarian.objects.create(user=request.user, name=name, email=email )  # Create a librarian instance
        elif role == 'patron':
            Patron.objects.create(user=request.user, name=name , email=email )  # Create a patron instance
        
        return redirect('home')  # Redirect to the home page after selecting a role
    
    return render(request, 'account/role_select.html')
