from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem
from .forms import SimpleItemForm, ComplexItemForm

def index(request):
    return render(request, 'borrow/index.html')

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        # Get all items (SimpleItems and ComplexItems) from the database
        return Item.objects.all().order_by("name")


class DetailView(generic.DetailView):
    model = Item
    template_name = "borrow/detail.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        item = self.get_object()
        
        # Get the BorrowedItem instances related to this item (whether it's simple or complex)
        borrowed_items = BorrowedItem.objects.filter(item=item)
        
        # Create a list of dictionaries with borrower names and the quantities they borrowed
        borrowers_info = []
        for borrowed_item in borrowed_items:
            borrowers_info.append({
                "borrower_name": borrowed_item.borrower.name,
                "borrowed_quantity": borrowed_item.quantity,
                "due_date": borrowed_item.due_date,
                "is_late": borrowed_item.is_late()
            })
        
        # Add the additional data to the context
        context['borrowers_info'] = borrowers_info
        return context

@login_required
def add_item(request):
    # Check if the user is a Librarian and has permission to add items
    if isinstance(request.user, Librarian) and request.user.can_add_items:
        if request.method == 'POST':
            # Determine the selected item type from the form
            item_type = request.POST.get('item_type')
            if item_type == 'simple':
                return redirect('borrow:add_simple_item')  # Redirect to the SimpleItem form
            elif item_type == 'complex':
                return redirect('borrow:add_complex_item')  # Redirect to the ComplexItem form
        return render(request, 'choose_item_type.html')  # Show the item type selection page
    else:
        return HttpResponseForbidden("You do not have permission to add items.")


@login_required
def add_simple_item(request):
    if isinstance(request.user, Librarian) and request.user.can_add_items:
        if request.method == 'POST':
            form = SimpleItemForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                return redirect('item_list')  # Redirect to item list or another view
        else:
            form = SimpleItemForm()
        
        return render(request, 'add_item.html', {'form': form, 'item_type': 'Simple Item'})
    else:
        return HttpResponseForbidden("You do not have permission to add items.")

@login_required
def add_complex_item(request):
    if isinstance(request.user, Librarian) and request.user.can_add_items:
        if request.method == 'POST':
            form = ComplexItemForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                return redirect('item_list')  # Redirect to item list or another view
        else:
            form = ComplexItemForm()

        return render(request, 'add_item.html', {'form': form, 'item_type': 'Complex Item'})
    else:
        return HttpResponseForbidden("You do not have permission to add items.")
