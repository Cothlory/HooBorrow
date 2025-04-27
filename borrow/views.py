from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q


from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron, Collections, BorrowRequest, Review, CollectionRequest, CollectionItemAllocation
from .forms import SimpleItemForm, ComplexItemForm, QuantityForm, CollectionForm, ReviewForm, CollectionRequestForm

def index(request):
    return render(request, 'borrow/index.html')

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        qs = Item.objects.all().order_by('name')
        cat = self.request.GET.get('category')
        if cat in dict(Item.CATEGORY_CHOICES):
            qs = qs.filter(category=cat)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(location__icontains=q)
                | Q(instructions__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['CategoryChoices'] = Item.CATEGORY_CHOICES
        context['current_category'] = self.request.GET.get('category','')
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
            messages.warning(request, "You don't have permission to view this item.", extra_tags='current-page')
            return redirect('borrow:index')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        
        # Get borrowed items
        borrowed_items = BorrowedItem.objects.filter(item=item, returned=False)
        borrowers_info = []
        for borrowed_item in borrowed_items:
            borrowers_info.append({
                'borrower_name': borrowed_item.borrower.name,
                'borrowed_quantity': borrowed_item.quantity,
                'due_date': borrowed_item.due_date,
                'is_late': borrowed_item.is_late()
            })
        
        context['borrowers_info'] = borrowers_info
        
        # Get reviews
        reviews = item.reviews.all().order_by('-created_at')
        context['reviews'] = reviews
        
        # Check if user can review
        if self.request.user.is_authenticated:
            try:
                patron = Patron.objects.get(user=self.request.user)
                context['can_review'] = True
                context['has_reviewed'] = item.reviews.filter(reviewer=patron).exists()
            except Patron.DoesNotExist:
                context['can_review'] = False
        else:
            context['can_review'] = False
        
        # Check if user has borrowed this item
        if self.request.user.is_authenticated:
            try:
                patron = Patron.objects.get(user=self.request.user)
                context['borrowed'] = BorrowedItem.objects.filter(
                    borrower=patron,
                    item=item,
                    returned=False
                ).exists()
            except Patron.DoesNotExist:
                context['borrowed'] = False
        else:
            context['borrowed'] = False
            
        return context

def borrow_item(request, pk):
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        return redirect('account:profile')  # Redirect if not a Patron
    
    # get item from the list
    item = get_object_or_404(Item, pk=pk)
    
    # Check if user can view this item
    if not item.can_view(request.user):
        messages.error(request, "You don't have permission to borrow this item.", extra_tags='current-page')
        return redirect('borrow:index')

    # Create a form instance with POST data if the form is submitted
    form = QuantityForm(request.POST or None)
    
    if request.method == "POST" and form.is_valid():
        quantity = form.cleaned_data['quantity']
        
        # Validate quantity against available
        if quantity <= 0 or quantity > item.quantity:
            messages.error(request, f"Invalid quantity. Available: {item.quantity}", extra_tags='current-page')
            return render(request, 'borrow/borrow.html', {'form': form, 'item': item})
            
        borrow_request = BorrowRequest.objects.create(
            borrower=patron, 
            item=item, 
            quantity=quantity, 
            date=timezone.now()
        )
        messages.success(request, 'Your borrow request has been sent to the librarian.', extra_tags='current-page')
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
            messages.error(request, "Borrow request not found.", extra_tags='current-page')
            return redirect('borrow:approve_requests')

        if action == 'approve':
            try: 
                item = borrow_request.item
                # Determine whether it's a simple or complex item based on attributes
                # rather than class type
                is_complex = hasattr(item, 'condition')
                
                # Use the patron's generic borrow_item method which works with any Item
                success = borrow_request.borrower.borrow_item(
                    item=item, 
                    quantity=borrow_request.quantity
                )
                
                if success:
                    # Mark the BorrowRequest as approved
                    borrow_request.status = BorrowRequest.APPROVED
                    borrow_request.save()
                    messages.success(request, f"Request for {borrow_request.quantity} of {item.name} has been approved.", extra_tags='current-page')
                else:
                    messages.error(request, f"Item borrowing failed for {item.name}. Please check the available quantity.", extra_tags='current-page')
            except Exception as e:
                messages.error(request, f"Error occurred while approving the request: {str(e)}", extra_tags='current-page')
                return redirect('borrow:approve_requests')

        elif action == 'reject':
            borrow_request.status = BorrowRequest.REJECTED
            borrow_request.save()
            messages.error(request, f"Request for {borrow_request.item.name} has been rejected.", extra_tags='current-page')

        return redirect('borrow:approve_requests')  # Redirect to the same page to refresh the list

    return render(request, 'borrow/approve.html', {'borrow_requests': borrow_requests})

@login_required
def add_item(request):
    # Only librarians can reach this
    try:
        Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

    if request.method == 'POST':
        # Grab the selected category from the form POST
        category = request.POST.get('category', Item.CATEGORY_OTHER)

        # Redirect to the appropriate form, appending ?category=
        if category == Item.CATEGORY_BALLS:
            return redirect(f"{reverse('borrow:add_simple_item')}?category={category}")
        else:
            return redirect(f"{reverse('borrow:add_complex_item')}?category={category}")

    # GET: render the chooser with the category options
    return render(request, 'borrow/choose_item_type.html', {
        'CategoryChoices': Item.CATEGORY_CHOICES
    })


@login_required
def add_simple_item(request):
    # only librarians can add
    try:
        Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

    # pick up the category from the querystring (default to OTHER)
    category = request.GET.get('category', Item.CATEGORY_OTHER)

    if request.method == 'POST':
        form = SimpleItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            # ensure the chosen category is applied
            item.category = form.cleaned_data.get('category', category)
            item.save()
            return redirect('home')
    else:
        # pre-fill the hidden category field
        form = SimpleItemForm(initial={'category': category})

    return render(request, 'borrow/add_simple_item.html', {
        'form': form,
        'item_type': 'Simple Item',
    })


@login_required
def add_complex_item(request):
    # only librarians can add
    try:
        Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")

    # pick up the category from the querystring (default to OTHER)
    category = request.GET.get('category', Item.CATEGORY_OTHER)

    if request.method == 'POST':
        form = ComplexItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            # ensure the chosen category is applied
            item.category = form.cleaned_data.get('category', category)
            item.save()
            return redirect('home')
    else:
        # pre-fill the hidden category field
        form = ComplexItemForm(initial={'category': category})

    return render(request, 'borrow/add_complex_item.html', {
        'form': form,
        'item_type': 'Complex Item',
    })

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
            messages.error(request, "Patron not found.", extra_tags='current-page')

        user = patron.user
        name = patron.name
        email = patron.email
        
        # Check if the user is already a librarian
        if isinstance(patron, Librarian):
            messages.error(request, f"{name} is already a librarian.", extra_tags='current-page')
        else:
            patron.delete() 
            # Promote patron to librarian
            librarian = Librarian.objects.create(user=user, name=name, email=email)
            librarian.save()

            messages.success(request, f"{patron.name} has been promoted to Librarian.", extra_tags='current-page')
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
    
    if is_librarian:
        collections = Collections.objects.all().order_by("title")
    else:
        collections = Collections.objects.filter(creator=creator).order_by("title")
    
    return render(request, 'borrow/manage_collections.html', {
        'collections': collections,
        'is_librarian': is_librarian,
    })

@login_required
def edit_collection(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        is_librarian = False
        creator = Patron.objects.get(user=request.user)
    
    if is_librarian:
        collection = get_object_or_404(Collections, pk=pk)
    else:
        collection = get_object_or_404(Collections, pk=pk, creator=creator)
    
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection, 
                          librarian=librarian if is_librarian else creator,
                          is_librarian=is_librarian,
                          editing=True)
        if form.is_valid():
            form.save()
            
            # Process item removals
            for key, value in request.POST.items():
                if key.startswith('remove_item_') and value == '1':
                    item_id = key.replace('remove_item_', '')
                    try:
                        item = Item.objects.get(id=item_id)
                        message = collection.remove_item(item)
                        messages.info(request, message, extra_tags='current-page')
                    except Item.DoesNotExist:
                        messages.error(request, f"Item not found", extra_tags='current-page')
                    except ValueError as e:
                        messages.error(request, str(e), extra_tags='current-page')
            
            # Process new items - they are submitted as hidden inputs with name new_item_[id]
            for key, value in request.POST.items():
                if key.startswith('new_item_'):
                    item_id = int(key.replace('new_item_', ''))
                    
                    try:
                        # Get the original item
                        original_item = Item.objects.get(id=item_id, is_original=True)
                        
                        if collection.is_collection_private:
                            # For private collections, validate and use quantity
                            quantity = int(value)
                            if quantity <= 0 or quantity > original_item.quantity:
                                messages.error(request, 
                                    f"Invalid quantity for {original_item.name}: {quantity}. Available: {original_item.quantity}",
                                    extra_tags='current-page')
                                continue
                                
                            # Add item to collection with specified quantity
                            collection.add_item(original_item, quantity)
                            messages.success(request, 
                                f"Added {quantity} of {original_item.name} to collection",
                                extra_tags='current-page')
                        else:
                            # For public collections, ignore quantity - just add a reference
                            collection.add_item(original_item, 0)
                            messages.success(request, 
                                f"Added {original_item.name} to collection",
                                extra_tags='current-page')
                    except Item.DoesNotExist:
                        messages.error(request, f"Item not found", extra_tags='current-page')
                    except ValueError as e:
                        messages.error(request, str(e), extra_tags='current-page')
            
            messages.success(request, 'Collection updated successfully.', extra_tags='current-page')
            return redirect('borrow:collection_detail', pk=collection.pk)
    else:
        form = CollectionForm(instance=collection, 
                          librarian=librarian if is_librarian else creator, 
                          is_librarian=is_librarian,
                          editing=True)
    
    return render(request, 'borrow/edit_collection.html', {
        'form': form,
        'collection': collection,
        'is_librarian': is_librarian
    })

@login_required
def delete_collection(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        is_librarian = False
        creator = Patron.objects.get(user=request.user)

    if is_librarian:
        collection = get_object_or_404(Collections, pk=pk)
    else:
        collection = get_object_or_404(Collections, pk=pk, creator=creator)

    if request.method == 'POST':
        # Return all items to their original inventory
        returned_items = collection.return_all_items()
        
        # Log what happened
        for item in returned_items:
            messages.info(
                request,
                f"Returned {item['quantity']} of '{item['name']}' to original inventory",
                extra_tags='current-page'
            )
        
        # Now delete the collection
        collection_name = collection.title
        collection.delete()
        
        messages.success(
            request,
            f"Collection '{collection_name}' deleted successfully",
            extra_tags='current-page'
        )
        return redirect('borrow:manage_collections')
    
    return render(request, 'borrow/delete_collection_confirm.html', {
        'collection': collection
    })

class CollectionDetailView(generic.DetailView):
    model = Collections
    template_name = "borrow/collection_detail.html"

    def dispatch(self, request, *args, **kwargs):
        collection = self.get_object()
        if collection.is_collection_private and not collection.can_view(request.user):
            messages.warning(request, "This is a private collection.", extra_tags='current-page')
        return super().dispatch(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collection = self.get_object()
        
        # Get visible items based on user permissions
        visible_items = []
        for item in collection.items_list:
            if item.can_view(self.request.user):
                visible_items.append(item)
                
        context['visible_items'] = visible_items
        return context

@login_required
def add_review(request, pk):
    item = get_object_or_404(Item, pk=pk)
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        messages.error(request, "Only patrons can review items.", extra_tags='current-page')
        return redirect('borrow:detail', pk=pk)
    borrowed_history = BorrowedItem.objects.filter(borrower=patron, item=item).exists()
    if not borrowed_history:
        messages.error(request, "You can only review items you've borrowed.", extra_tags='current-page')
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
            messages.success(request, "Your review has been submitted!", extra_tags='current-page')
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
        messages.error(request, "You need to be a patron to see borrowed items.", extra_tags='current-page')
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
            messages.error(request, f"Invalid quantity. You can return between 1 and {borrowed_item.quantity} items.", extra_tags='current-page')
            return render(request, 'borrow/return_item.html', {'borrowed_item': borrowed_item})
        
        # Return to the correct item
        item = borrowed_item.item
        
        # Add the quantity back
        item.quantity += quantity_to_return
        item.save()
        
        # Update the borrowed record
        borrowed_item.quantity -= quantity_to_return
        if borrowed_item.quantity <= 0:
            borrowed_item.returned = True
        borrowed_item.save()
        
        messages.success(request, f"Successfully returned {quantity_to_return} of {item.name}.", extra_tags='current-page')
        
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
            messages.error(request, "Collection request not found.", extra_tags='current-page')
            return redirect('borrow:approve_collection_requests')

        if action == 'approve':
            collection = collection_request.collection
            user = collection_request.user
            try:
                collection.allowed_users.add(user)
                collection_request.status = CollectionRequest.APPROVED
                collection_request.save()
                messages.success(request, "Collection request has been approved.", extra_tags='current-page')
            except Exception as e:
                messages.error(request, f"Error occurred while approving the request: {str(e)}", extra_tags='current-page')
                return redirect('borrow:approve_collection_requests')

        elif action == 'reject':
            collection_request.status = CollectionRequest.REJECTED
            collection_request.save()
            messages.error(request, f"Request for {collection_request.collection.title} has been rejected.", extra_tags='current-page')

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
        messages.success(request, 'Your request to join this collection has been sent to the librarian.', extra_tags='current-page')
        return redirect('borrow:collection_detail', pk=pk)

    return render(request, 'borrow/request_collection.html', {'form': form, 'collection': collection})

@login_required
def create_collection(request):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        is_librarian = False
        patron = Patron.objects.get(user=request.user)
    
    if request.method == 'POST':
        form = CollectionForm(request.POST, 
                          librarian=librarian if is_librarian else patron,
                          is_librarian=is_librarian)
        if form.is_valid():
            collection = form.save()
            messages.success(request, f"Collection '{collection.title}' created successfully. You can now add items.", 
                         extra_tags='current-page')
            return redirect('borrow:edit_collection', pk=collection.pk)
    else:
        form = CollectionForm(librarian=librarian if is_librarian else patron,
                          is_librarian=is_librarian)
    
    return render(request, 'borrow/create_collection.html', {
        'form': form,
        'is_librarian': is_librarian,
    })

@login_required
def manage_items(request):
    try:
        librarian = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        messages.error(request, "You don't have permission to manage items.", extra_tags='current-page')
        return redirect('home')

    simple_items = SimpleItem.objects.all()
    complex_items = ComplexItem.objects.all()
    items = list(simple_items) + list(complex_items)
    items.sort(key=lambda x: x.name)
    
    return render(request, 'borrow/manage_items.html', {
        'items': items,
    })

@login_required
def edit_item(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        messages.error(request, "You don't have permission to edit items.", extra_tags='current-page')
        return redirect('home')
    
    try:
        item = SimpleItem.objects.get(pk=pk)
        form_class = SimpleItemForm
        template = 'borrow/edit_simple_item.html'
    except SimpleItem.DoesNotExist:
        try:
            item = ComplexItem.objects.get(pk=pk)
            form_class = ComplexItemForm
            template = 'borrow/edit_complex_item.html'
        except ComplexItem.DoesNotExist:
            messages.error(request, "Item not found.", extra_tags='current-page')
            return redirect('borrow:manage_items')
    
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Item '{item.name}' has been updated successfully.", extra_tags='current-page')
            return redirect('borrow:manage_items')
    else:
        form = form_class(instance=item)
    
    return render(request, template, {
        'form': form,
        'item': item,
    })

def search_items(request):
    query = request.GET.get('q', '')
    items = Item.objects.filter(is_original=True)  # Only search original items
    
    if query:
        items = items.filter(name__icontains=query)
    
    # Only show items with quantity > 0
    items = items.filter(quantity__gt=0)
    
    # Limit results
    items = items[:20]  
    
    results = []
    for item in items:
        results.append({
            'id': item.id,
            'name': item.name,
            'quantity': item.quantity,
            'available_quantity': item.quantity,  # For original items, all quantity is available
        })
    
    return JsonResponse(results, safe=False)

def search_users(request):
    """API endpoint to search for users that can be added to collections"""
    query = request.GET.get('q', '')
    
    # Only librarians should access this
    try:
        librarian = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    # Search for patrons matching the query
    patrons = Patron.objects.filter(
        Q(name__icontains=query) | Q(email__icontains=query)
    )[:20]  # Limit results
    
    results = []
    for patron in patrons:
        results.append({
            'id': patron.id,
            'name': patron.name,
            'email': patron.email,
        })
    
    return JsonResponse(results, safe=False)
