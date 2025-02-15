from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.utils import timezone

from .models import ItemCategory, BorrowedItem

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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # get the ItemCategory instance
        item_category = self.get_object()
        
        # get the borrowers related to this ItemCategory
        borrowed_items = BorrowedItem.objects.filter(category=item_category)
        
        # create a list of dictionaries with borrower names and the quantities they borrowed
        borrowers_info = []
        for borrowed_item in borrowed_items:
            borrowers_info.append({
                "borrower_name": borrowed_item.borrower.name,
                "borrowed_quantity": borrowed_item.quantity,
                "due_date": borrowed_item.due_date,
                "is_late": borrowed_item.is_late()
            })
        
        # add the additional data to the context
        context['borrowers_info'] = borrowers_info
        return context
