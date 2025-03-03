from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required


def home(request):
    return render(request, "home.html")

@login_required
def profile_view(request):
    role = "librarian" if request.user.is_staff else "patron"
    return render(request, 'account/profile.html', {'role': role})
