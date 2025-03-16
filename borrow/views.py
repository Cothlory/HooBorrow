from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron
from .forms import SimpleItemForm, ComplexItemForm, QuantityForm

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

def borrow_item(request, pk):
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        return redirect('account:profile')  # Redirect if not a Patron
    
    try:
        simpleitem = SimpleItem.objects.get(pk=pk)
        complexitem = None
    except SimpleItem.DoesNotExist:
        simpleitem = None
        try:
            complexitem = ComplexItem.objects.get(pk=pk)
        except ComplexItem.DoesNotExist:
            return HttpResponseNotFound("Item not found")
    
    # Create a form instance with POST data if the form is submitted
    form = QuantityForm(request.POST or None)
    
    if request.method == "POST" and form.is_valid():
        quantity = form.cleaned_data['quantity']
        
        success = False
        
        if simpleitem:
            success = patron.borrow_simple_item(simpleitem, quantity)
        elif complexitem:
            success = patron.borrow_complex_item(complexitem)

        
        if success:
            return redirect('borrow:detail', pk=pk)
        else:
            messages.error(request, "Item borrowing failed. Please try again.")
            return redirect('borrow:borrow_item', pk=pk) # give feedback to user 

    
    context = {
        'item': simpleitem if simpleitem else complexitem,
        'item_type': 'simple' if simpleitem else 'complex', 
        'form': form,
    }
    return render(request, 'borrow/borrow.html', context)

@login_required
def add_item(request):
    # Check if the user has a related Librarian instance and if they have permission to add items
    try:
        librarian = Librarian.objects.get(user=request.user)  # Try to get the librarian instance
        if librarian.can_add_items:  # Check if they have permission
            if request.method == 'POST':
                # Determine the selected item type from the form
                item_type = request.POST.get('item_type')
                if item_type == 'simple':
                    return redirect('borrow:add_simple_item')  # Redirect to the SimpleItem form
                elif item_type == 'complex':
                    return redirect('borrow:add_complex_item')  # Redirect to the ComplexItem form
            return render(request, 'borrow/choose_item_type.html')  # Show the item type selection page
        else:
            return HttpResponseForbidden("You do not have permission to add items.")  # User doesn't have permission
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")  # If the user is not a librarian


def add_simple_item(request):
    try:
        librarian = Librarian.objects.get(user=request.user) 
        if librarian.can_add_items:
            if request.method == 'POST':
                form = SimpleItemForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    return redirect('home')  # Redirect to item list or another view
            else:
                form = SimpleItemForm()
            
            return render(request, 'borrow/add_simple_item.html', {'form': form, 'item_type': 'Simple Item'})
        else:
            return HttpResponseForbidden("You do not have permission to add items.")
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

def add_complex_item(request):
    try:
        librarian = Librarian.objects.get(user=request.user) 
        if librarian.can_add_items:
            if request.method == 'POST':
                form = ComplexItemForm(request.POST, request.FILES)
                if form.is_valid():
                    form.save()
                    return redirect('home')  # Redirect to item list or another view
            else:
                form = ComplexItemForm()

            return render(request, 'borrow/add_complex_item.html', {'form': form, 'item_type': 'Complex Item'})
        else:
            return HttpResponseForbidden("You do not have permission to add items.")
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")