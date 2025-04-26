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
    # Try to get the existing Patron instance
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        # Only create a new one if it doesn't exist
        patron = Patron.objects.create(
            user=request.user,
            email=request.user.email,
            name=request.user.get_full_name(),
        )
        # Redirect to ensure smooth flow
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

    return render(request, 'account/profile.html', {'role': role, 'patron': patron})
