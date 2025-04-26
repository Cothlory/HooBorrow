from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from borrow.models import Librarian, Patron 
from allauth.socialaccount.models import SocialAccount


def home(request):
    return render(request, "home.html")

@login_required
def profile_view(request):
    # Ensure the user has a Patron instance; if not, create one
    patron, created = Patron.objects.get_or_create(user=request.user, email = request.user.email, name = request.user.get_full_name())

    # If a new Patron object was just created, redirect to profile to ensure smooth flow
    if created:
        return redirect('profile')

    # Check if the user has a Librarian instance
    librarian = Librarian.objects.filter(user=request.user).first()
    
    # Determine user role: librarian > patron > unknown
    if librarian:
        role = "librarian"
    elif patron:
        role = "patron"
    else:
        role = "unknown"

    # Handle profile photo upload
    if request.method == 'POST' and request.FILES.get('profile_photo'):
        patron.profile_photo = request.FILES['profile_photo']
        patron.save()
        return redirect('profile')

    return render(request, 'account/profile.html', {'role': role})

def redirect_to_home(request):
    """Redirect users trying to access AllAuth pages to the home page with a message"""
    messages.info(request, "Please use Google login to sign in or register.", extra_tags='current-page')
    return HttpResponseRedirect(reverse('home'))
