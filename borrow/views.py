from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron, Collections, BorrowRequest, Review, CollectionRequest
from .forms import SimpleItemForm, ComplexItemForm, QuantityForm, CollectionForm, ReviewForm, CollectionRequestForm

def index(request):
    return render(request, 'borrow/index.html')

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        return Item.objects.all().order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['collections_list'] = Collections.objects.all().order_by("title")
        else:
            context['collections_list'] = Collections.objects.filter(is_collection_private=False).order_by("title")
        return context


class DetailView(generic.DetailView):
    model = Item
    template_name = "borrow/detail.html"
    
    def dispatch(self, request, *args, **kwargs):
        item = self.get_object()
        if not item.can_view(request.user):
            return HttpResponseForbidden("You do not have permission to view this item.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        borrowed_items = BorrowedItem.objects.filter(item=item)
        borrowers_info = []
        for borrowed_item in borrowed_items:
            borrowers_info.append({
                "borrower_name": borrowed_item.borrower.name,
                "borrowed_quantity": borrowed_item.quantity,
                "due_date": borrowed_item.due_date,
                "is_late": borrowed_item.is_late()
            })
        context['borrowers_info'] = borrowers_info
        reviews = item.reviews.all().order_by('-created_at')
        context['reviews'] = reviews
        if self.request.user.is_authenticated:
            try:
                patron = Patron.objects.get(user=self.request.user)
                has_borrowed = BorrowedItem.objects.filter(borrower=patron, item=item).exists()
                has_reviewed = Review.objects.filter(reviewer=patron, item=item).exists()
                context['can_review'] = has_borrowed
                context['has_reviewed'] = has_reviewed
            except Patron.DoesNotExist:
                context['can_review'] = False
                context['has_reviewed'] = False
        else:
            context['can_review'] = False
            context['has_reviewed'] = False
            
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
    try:
        librarian = Librarian.objects.get(user=request.user) 
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot approve requests.")

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
            try: 
                item = borrow_request.item
                success = False

                try:
                    # Try to get the item as a SimpleItem
                    simple_item = SimpleItem.objects.get(id=item.id)
                    success = borrow_request.borrower.borrow_simple_item(simple_item, borrow_request.quantity)
                except SimpleItem.DoesNotExist:
                    # If it's not a SimpleItem, try ComplexItem
                    try:
                        complex_item = ComplexItem.objects.get(id=item.id)
                        success = borrow_request.borrower.borrow_complex_item(complex_item)
                    except ComplexItem.DoesNotExist:
                        messages.error(request, f"Item {item.name} not found in either Simple or Complex categories.")
                        return redirect('borrow:approve_requests')
                
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

    def dispatch(self, request, *args, **kwargs):
        collection = self.get_object()
        if collection.is_collection_private and not request.user.is_authenticated:
            return HttpResponseForbidden("You do not have permission to view this collection.")
        return super().dispatch(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collection = self.get_object()
        user = self.request.user
        if not collection.is_collection_private:
            visible_items = collection.items_list.all()
        else:
            from .models import Librarian
            if user.is_authenticated and Librarian.objects.filter(user=user).exists():
                visible_items = collection.items_list.all()
            elif user.is_authenticated and collection.allowed_users.filter(pk=user.patron.pk).exists():
                visible_items = collection.items_list.all()
            else:
                visible_items = []
        context['visible_items'] = visible_items
        return context

@login_required
def add_review(request, pk):
    item = get_object_or_404(Item, pk=pk)
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        messages.error(request, "Only patrons can review items.")
        return redirect('borrow:detail', pk=pk)
    borrowed_history = BorrowedItem.objects.filter(borrower=patron, item=item).exists()
    if not borrowed_history:
        messages.error(request, "You can only review items you've borrowed.")
        return redirect('borrow:detail', pk=pk)
    existing_review = Review.objects.filter(reviewer=patron, item=item).first()
    
    if request.method == 'POST':
        if existing_review:
            form = ReviewForm(request.POST, instance=existing_review)
        else:
            form = ReviewForm(request.POST)
        
        if form.is_valid():
            review = form.save(commit=False)
            review.item = item
            review.reviewer = patron
            review.save()
            messages.success(request, "Your review has been submitted!")
            return redirect('borrow:detail', pk=pk)
    else:
        if existing_review:
            form = ReviewForm(instance=existing_review)
        else:
            form = ReviewForm()
    
    return render(request, 'borrow/add_review.html', {
        'form': form,
        'item': item,
        'existing_review': existing_review
    })

@login_required
def my_borrowed_items(request):
    try:
        patron = Patron.objects.get(user=request.user)
        borrowed_items = BorrowedItem.objects.filter(borrower=patron, returned=False)
        return render(request, 'borrow/my_borrowed_items.html', {'borrowed_items': borrowed_items})
    except Patron.DoesNotExist:
        messages.error(request, "You need to be a patron to see borrowed items.")
        return redirect('home')

@login_required
def all_borrowed_items(request):
    try:
        librarian = Librarian.objects.get(user=request.user)
        borrowed_items = BorrowedItem.objects.filter(returned=False)
        return render(request, 'borrow/all_borrowed_items.html', {'borrowed_items': borrowed_items})
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot view all borrowed items.")

@login_required
def return_item(request, borrowed_item_id):
    borrowed_item = get_object_or_404(BorrowedItem, id=borrowed_item_id, returned=False)
    
    is_borrower = False
    is_librarian = False
    
    try:
        patron = Patron.objects.get(user=request.user)
        is_borrower = (patron == borrowed_item.borrower)
    except Patron.DoesNotExist:
        pass
    
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        pass
    
    if not (is_borrower or is_librarian):
        return HttpResponseForbidden("You do not have permission to return this item.")
    
    if request.method == "POST":
        quantity_to_return = int(request.POST.get('quantity', 1))
        
        if quantity_to_return <= 0 or quantity_to_return > borrowed_item.quantity:
            messages.error(request, f"Invalid quantity. You can return between 1 and {borrowed_item.quantity} items.")
            return redirect('borrow:my_borrowed_items' if is_borrower else 'borrow:all_borrowed_items')
        
        item = borrowed_item.item
        success = False
        
        if borrowed_item.item_type == 'SIMPLE':
            try:
                simple_item = SimpleItem.objects.get(id=item.id)
                if is_borrower:
                    success = borrowed_item.borrower.return_simple_item(simple_item, quantity_to_return)
                else:  
                    simple_item.quantity += quantity_to_return
                    simple_item.save()
                    
                    borrowed_item.quantity -= quantity_to_return
                    if borrowed_item.quantity == 0:
                        borrowed_item.returned = True
                    borrowed_item.save()
                    success = True
            except SimpleItem.DoesNotExist:
                messages.error(request, f"Item {item.name} not found as a Simple Item.")
        else: 
            try:
                complex_item = ComplexItem.objects.get(id=item.id)
                if is_borrower:
                    success = borrowed_item.borrower.return_complex_item(complex_item, quantity_to_return)
                else: 
                    complex_item.quantity += quantity_to_return
                    complex_item.save()
                    
                    borrowed_item.quantity -= quantity_to_return
                    if borrowed_item.quantity == 0:
                        borrowed_item.returned = True
                    borrowed_item.save()
                    success = True
            except ComplexItem.DoesNotExist:
                messages.error(request, f"Item {item.name} not found as a Complex Item.")
        
        if success:
            messages.success(request, f"Successfully returned {quantity_to_return} of {item.name}.")
        else:
            messages.error(request, f"Failed to return {item.name}. Please try again.")
        
        if is_borrower:
            return redirect('borrow:my_borrowed_items')
        else:
            return redirect('borrow:all_borrowed_items')
    
    return render(request, 'borrow/return_item.html', {'borrowed_item': borrowed_item})

@login_required
def approve_collection_requests(request):
    try:
        librarian = Librarian.objects.get(user=request.user) 
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot approve requests.")

    # Fetch all the borrow requests that are PENDING
    collection_requests = CollectionRequest.objects.filter(status=CollectionRequest.PENDING)

    if request.method == "POST":
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')  # 'approve' or 'reject'

        try:
            collection_request = CollectionRequest.objects.get(id=request_id)
        except CollectionRequest.DoesNotExist:
            messages.error(request, "Collection request not found.")
            return redirect('borrow:approve_collection_requests')

        if action == 'approve':
            collection = collection_request.collection
            user = collection_request.user
            try:
                collection.allowed_users.add(user)
                collection_request.status = CollectionRequest.APPROVED
                collection_request.save()
                messages.success(request, "Collection request has been approved.")
            except Exception as e:
                messages.error(request, f"Error occurred while approving the request: {str(e)}")
                return redirect('borrow:approve_collection_requests')

        elif action == 'reject':
            collection_request.status = CollectionRequest.REJECTED
            collection_request.save()
            messages.error(request, f"Request for {collection_request.collection.title} has been rejected.")

        return redirect('borrow:approve_collection_requests')  # Redirect to the same page to refresh the list

    return render(request, 'borrow/approve_collection_requests.html', {'collection_requests': collection_requests})

@login_required
def request_collection(request, pk):
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        return redirect('account:profile')  # Redirect if not a Patron
    
    # get collection from the list
    collection = Collections.objects.get(pk=pk)

    # Create a form instance with POST data if the form is submitted
    form = CollectionRequestForm(request.POST or None)
    
    if request.method == "POST" and form.is_valid():
        notes = form.cleaned_data['notes']
        collection_request = CollectionRequest.objects.create(user=patron, collection=collection, notes=notes, date= timezone.now())
        print(request)
        collection_request.save()
        messages.success(request, 'Your request to join this collection has been sent to the librarian.')
        return redirect('borrow:collection_detail', pk=pk)

    return render(request, 'borrow/request_collection.html', {'form': form, 'collection': collection})