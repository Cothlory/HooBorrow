from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron, Collections, BorrowRequest
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
    
    # get item from the list
    item = Item.objects.get(pk=pk)
    print(item)

    # Create a form instance with POST data if the form is submitted
    form = QuantityForm(request.POST or None)
    
    if request.method == "POST" and form.is_valid():
        quantity = form.cleaned_data['quantity']
        borrow_request = BorrowRequest.objects.create(borrower=patron, item=item, quantity=quantity, date= timezone.now())
        print(request)
        borrow_request.save()
        messages.success(request, 'Your borrow request has been sent to the librarian.')
        return redirect('borrow:detail', pk=pk)

    return render(request, 'borrow/borrow.html', {'form': form, 'item': item})


def approve_requests(request):
    # Fetch all the borrow requests that are PENDING
    borrow_requests = BorrowRequest.objects.filter(status=BorrowRequest.PENDING)

    if request.method == "POST":
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')  # 'approve' or 'reject'

        try:
            borrow_request = BorrowRequest.objects.get(id=request_id)
        except BorrowRequest.DoesNotExist:
            messages.error(request, "Borrow request not found.")
            return redirect('borrow:approve_requests')

        if action == 'approve':
            # Approve the request and create a BorrowedItem
            try:
                # Check if the item is Simple or Complex
                item = borrow_request.item

                # Create a BorrowedItem based on the type of item
                if isinstance(item, SimpleItem):
                    # Assuming you have a method in Patron to handle borrowing SimpleItems
                    success = borrow_request.borrower.borrow_simple_item(item, borrow_request.quantity)
                elif isinstance(item, ComplexItem):
                    # Assuming you have a method in Patron to handle borrowing ComplexItems
                    success = borrow_request.borrower.borrow_complex_item(item)

                if success:
                    # Mark the BorrowRequest as approved
                    borrow_request.status = BorrowRequest.APPROVED
                    borrow_request.save()

                    messages.success(request, f"Request for {borrow_request.quantity} of {item.name} has been approved.")
                else:
                    messages.error(request, f"Item borrowing failed for {borrow_request.item.name}. Please try again.")

            except Exception as e:
                messages.error(request, f"Error occurred while approving the request: {str(e)}")
                return redirect('borrow:approve_requests')

        elif action == 'reject':
            # Reject the request
            borrow_request.status = BorrowRequest.REJECTED
            borrow_request.save()
            messages.error(request, f"Request for {borrow_request.item.name} has been rejected.")

        return redirect('borrow:approve_requests')  # Redirect to the same page to refresh the list

    return render(request, 'borrow/approve.html', {'borrow_requests': borrow_requests})

@login_required
def add_item(request):
    try:
        librarian = Librarian.objects.get(user=request.user) 
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.") 

    if request.method == 'POST':
        # Determine the selected item type from the form
        item_type = request.POST.get('item_type')
        if item_type == 'simple':
            return redirect('borrow:add_simple_item')  # Redirect to the SimpleItem form
        elif item_type == 'complex':
            return redirect('borrow:add_complex_item')  # Redirect to the ComplexItem form
    return render(request, 'borrow/choose_item_type.html')  # Show the item type selection page


def add_simple_item(request):
    try:
        librarian = Librarian.objects.get(user=request.user) 
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

    if request.method == 'POST':
        form = SimpleItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to item list or another view
    else:
        form = SimpleItemForm()
    
    return render(request, 'borrow/add_simple_item.html', {'form': form, 'item_type': 'Simple Item'})


def add_complex_item(request):
    try:
        librarian = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

    if request.method == 'POST':
        form = ComplexItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to item list or another view
    else:
        form = ComplexItemForm()

    return render(request, 'borrow/add_complex_item.html', {'form': form, 'item_type': 'Complex Item'})


def manage_users(request):
    try:
        librarian = Librarian.objects.get(user=request.user)  # Try to get the librarian instance
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")
        
    patrons = Patron.objects.all()
    librarians = Librarian.objects.all()
    users = [] # Combine the users into a single list with role information
    for patron in patrons:
        role = 'Librarian' if Librarian.objects.filter(user=patron.user).exists() else 'Patron'
        users.append({
            'user': patron.user,
            'name': patron.name,
            'email': patron.email,
            'role': role
        })
    
    if request.method == 'POST':
        user_id = request.POST.get('promote_user_id')
        
        try:
            patron = Patron.objects.get(user__id=user_id)
        except Patron.DoesNotExist:
            messages.error(request, "Patron not found.")

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

    # If GET request, render the list of users
    return render(request, 'borrow/manage_users.html', {'users': users})


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
    
    collections = Collections.objects.filter(creator=creator)
    return render(request, 'borrow/manage_collections.html', {
        'form': form,
        'collections': collections,
        'is_librarian': is_librarian,
    })

@login_required
def edit_collection(request, pk):
    try:
        creator = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False

    collection = get_object_or_404(Collections, pk=pk, creator=creator)
    
    if request.method == "POST":
        form = CollectionForm(
            request.POST, 
            instance=collection, 
            librarian=creator, 
            is_librarian=is_librarian, 
            editing=True
        )
        if form.is_valid():
            instance = form.save(commit=False)
            instance.save()
            form.save_m2m()
            messages.success(request, f"Collection '{instance.title}' updated successfully.")
            return redirect("borrow:manage_collections")
        else:
            messages.error(request, f"Error saving collection: {form.errors}")
    else:
        form = CollectionForm(
            instance=collection, 
            librarian=creator, 
            is_librarian=is_librarian, 
            editing=True
        )
    
    return render(request, "borrow/edit_collection.html", {"form": form, "collection": collection})


@login_required
def delete_collection(request, pk):
    try:
        creator = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
    
    collection = get_object_or_404(Collections, pk=pk, creator=creator)
    
    if request.method == "POST":
        collection.delete()
        messages.success(request, f"Collection '{collection.title}' deleted successfully.")
        return redirect("borrow:manage_collections")
    
    return render(request, "borrow/confirm_delete_collection.html", {"collection": collection})

class CollectionDetailView(generic.DetailView):
    model = Collections
    template_name = "borrow/collection_detail.html"
