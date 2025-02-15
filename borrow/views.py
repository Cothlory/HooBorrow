from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic

from .models import ItemCategory

# def home(request):
#     return render(request, "home.html")

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        return ItemCategory.objects.all().order_by("name")

class DetailView(generic.DetailView):
    model = ItemCategory
    template_name = "borrow/detail.html"
