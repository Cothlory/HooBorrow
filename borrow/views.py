from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron, Collections
from .forms import SimpleItemForm, ComplexItemForm, QuantityForm, CollectionForm

def index(request):
    return render(request, 'borrow/index.html')

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        return Item.objects.all().order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collections_list'] = Collections.objects.all().order_by("title")
        return context


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


def manage_users(request):
    try:
        librarian = Librarian.objects.get(user=request.user)  # Try to get the librarian instance
        
        if librarian.can_add_items:
            patrons = Patron.objects.all()
            librarians = Librarian.objects.all()
            
            # Combine the users into a single list with role information
            users = []
            for patron in patrons:
                role = 'Librarian' if Librarian.objects.filter(user=patron.user).exists() else 'Patron'

                users.append({
                    'user': patron.user,
                    'name': patron.name,
                    'email': patron.email,
                    'role': role
                })
            print(users)
            
            if request.method == 'POST':
                user_id = request.POST.get('promote_user_id')
                
                try:
                    patron = Patron.objects.get(user__id=user_id)
                    user = patron.user
                    name = patron.name
                    email = patron.email
                    
                    # Check if the user is already a librarian
                    if isinstance(patron, Librarian):
                        messages.error(request, f"{name} is already a librarian.")
                    else:
                        patron.delete() 
                        # Promote patron to librarian
                        librarian = Librarian.objects.create(user=user, name=name, email=email)
                        librarian.save()

                        messages.success(request, f"{patron.name} has been promoted to Librarian.")
                        return redirect('borrow:manage_users')  # Redirect after successful promotion

                except Patron.DoesNotExist:
                    messages.error(request, "Patron not found.")

            # If GET request, render the list of users
            return render(request, 'borrow/manage_users.html', {'users': users})

        else: 
            return HttpResponseForbidden("You do not have permission to add items.")
    
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

@login_required
def manage_collections(request):
    try:
        creator = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False

    if request.method == "POST":
        form = CollectionForm(request.POST, librarian=creator, is_librarian=is_librarian)
        if form.is_valid():
            collection = form.save(commit=False)
            if not is_librarian:
                collection.is_collection_private = False
            collection.save()
            form.save_m2m()
            messages.success(request, f"Collection '{collection.title}' created.")
            return redirect('borrow:manage_collections')
    else:
        form = CollectionForm(librarian=creator, is_librarian=is_librarian)
    
    if is_librarian:
        collections = Collections.objects.all().order_by("title")
    else:
        collections = Collections.objects.filter(creator=creator).order_by("title")
    
    return render(request, 'borrow/manage_collections.html', {
        'form': form,
        'collections': collections,
        'is_librarian': is_librarian,
    })

@login_required
def edit_collection(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False
    
    if is_librarian:
        collection = get_object_or_404(Collections, pk=pk)
    else:
        collection = get_object_or_404(Collections, pk=pk, creator=creator)
    
    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection, librarian=librarian if is_librarian else creator, is_librarian=is_librarian, editing=True)
        if form.is_valid():
            form.save()
            messages.success(request, f"Collection '{collection.title}' updated successfully.")
            return redirect("borrow:manage_collections")
    else:
        form = CollectionForm(instance=collection, librarian=librarian if is_librarian else creator, is_librarian=is_librarian, editing=True)
    
    return render(request, "borrow/edit_collection.html", {"form": form, "collection": collection})


@login_required
def delete_collection(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False
    
    if is_librarian:
        collection = get_object_or_404(Collections, pk=pk)
    else:
        collection = get_object_or_404(Collections, pk=pk, creator=creator)
    
    if request.method == "POST":
        collection.delete()
        messages.success(request, f"Collection '{collection.title}' deleted successfully.")
        return redirect("borrow:manage_collections")
    
    return render(request, "borrow/confirm_delete_collection.html", {"collection": collection})

class CollectionDetailView(generic.DetailView):
    model = Collections
    template_name = "borrow/collection_detail.html"
