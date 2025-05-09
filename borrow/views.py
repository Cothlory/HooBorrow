from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q


from .models import Librarian, SimpleItem, ComplexItem, Item, BorrowedItem, Patron, Collections, BorrowRequest, Review, CollectionRequest, Message
from .forms import SimpleItemForm, ComplexItemForm, QuantityForm, CollectionForm, ReviewForm, CollectionRequestForm

def index(request):
    return render(request, 'borrow/index.html')

class IndexView(generic.ListView):
    template_name = "borrow/index.html"
    context_object_name = "borrow_items_list"

    def get_queryset(self):
        # Always return items queryset for the main list
        qs = Item.objects.all().order_by('name')
        
        # Get the active tab
        tab = self.request.GET.get('tab', 'items')
        
        # Only apply item filters if we're on the items tab or no tab is specified
        if tab != 'collections':
            # Category filtering
            cat = self.request.GET.get('category')
            if cat in dict(Item.CATEGORY_CHOICES):
                qs = qs.filter(category=cat)
            
            # Search filtering
            q = self.request.GET.get("q", "").strip()
            if q:
                qs = qs.filter(
                    Q(name__icontains=q)
                    | Q(location__icontains=q)
                    | Q(instructions__icontains=q)
                )
            
            # Add minimum quantity filtering
            min_quantity = self.request.GET.get('min_quantity')
            if min_quantity:
                try:
                    min_quantity = int(min_quantity)
                    qs = qs.filter(quantity__gte=min_quantity)
                except ValueError:
                    pass
            
            # Add item type filtering
            item_type = self.request.GET.get('item_type')
            if item_type == 'simple':
                # Filter for SimpleItems
                qs = qs.filter(simpleitem__isnull=False)
            elif item_type == 'complex':
                # Filter for ComplexItems
                qs = qs.filter(complexitem__isnull=False)
                
                # Add condition filtering for complex items
                condition = self.request.GET.get('condition')
                if condition:
                    # Use complexitem__condition to filter by condition
                    qs = qs.filter(complexitem__condition=condition)
        
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current tab
        context['current_tab'] = self.request.GET.get('tab', 'items')
        
        # Always include item context
        context['q'] = self.request.GET.get('q', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['min_quantity'] = self.request.GET.get('min_quantity', '1')
        context['item_type'] = self.request.GET.get('item_type', '')
        context['condition'] = self.request.GET.get('condition', '')
        
        # Always include collection context
        context['collection_q'] = self.request.GET.get('collection_q', '')
        context['collection_visibility'] = self.request.GET.get('collection_visibility', '')
        
        # Add collections_list to context
        collections = Collections.objects.all()
        
        # Apply collection filters if on collections tab
        if context['current_tab'] == 'collections':
            if context['collection_q']:
                collections = collections.filter(
                    Q(title__icontains=context['collection_q']) |
                    Q(description__icontains=context['collection_q'])
                )
            
            if context['collection_visibility'] == 'public':
                collections = collections.filter(is_collection_private=False)
            elif context['collection_visibility'] == 'private':
                collections = collections.filter(is_collection_private=True)
        
        # Filter private collections based on permissions
        if not self.request.user.is_authenticated:
            collections = collections.filter(is_collection_private=False)
        
        context['collections_list'] = collections
        
        # Add other context
        context['CategoryChoices'] = Item.CATEGORY_CHOICES
        context['ConditionChoices'] = ComplexItem.CONDITION_CHOICES
        
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
        borrowed_items = BorrowedItem.objects.filter(item=item, returned=False)
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
        avg_score = 0
        if reviews.exists():
            total_rating = sum(review.rating for review in reviews)
            avg_score = round(total_rating / reviews.count(), 1)
        context['avg_review_score'] = avg_score
        context['review_count'] = reviews.count()
        if self.request.user.is_authenticated:
            try:
                patron = Patron.objects.get(user=self.request.user)
                user_review = None
                for review in reviews:
                    if review.reviewer.user == self.request.user:
                        user_review = review
                        break
                if user_review:
                    reviews_list = list(reviews)
                    reviews_list.remove(user_review)
                    reviews_list.insert(0, user_review)
                    reviews = reviews_list
                
                has_borrowed = BorrowedItem.objects.filter(
                    borrower=patron,
                    item=item
                ).exists()
                has_reviewed = Review.objects.filter(
                    reviewer=patron,
                    item=item
                ).exists()
                
                context['can_review'] = has_borrowed
                context['has_reviewed'] = has_reviewed
            except Patron.DoesNotExist:
                context['can_review'] = False
                context['has_reviewed'] = False
        else:
            context['can_review'] = False
            context['has_reviewed'] = False
        
        context['reviews'] = reviews
        context['is_complex_item'] = hasattr(item, 'complexitem')
        return context

def borrow_item(request, pk):
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        return redirect('account:profile')  # Redirect if not a Patron
    
    # Get item from the list
    item = get_object_or_404(Item, pk=pk)
    
    # Check if it's a simple item or complex item
    is_simple_item = hasattr(item, 'simpleitem')
    is_complex_item = hasattr(item, 'complexitem')
    
    if is_simple_item:
        # Create a form instance with POST data if the form is submitted for Simple Items
        form = QuantityForm(request.POST or None)
        
        if request.method == "POST" and form.is_valid():
            quantity = form.cleaned_data['quantity']
            borrow_request = BorrowRequest.objects.create(
                borrower=patron, 
                item=item, 
                quantity=quantity, 
                date=timezone.now()
            )
            borrow_request.save()
            send_message_to_librarians(
                subject=f"New Borrow Request: {patron.name} - {item.name}",
                content=f"{patron.name} has requested to borrow {quantity} {item.name}.",
                link=reverse('borrow:approve_requests'),
                sender=patron
            )
            messages.success(request, 'Your borrow request has been sent to the librarian.', extra_tags='current-page')
            return redirect('borrow:detail', pk=pk)
        
        return render(request, 'borrow/borrow.html', {'form': form, 'item': item, 'is_simple_item': True})
    
    else:
        # For complex items - no quantity needed
        if request.method == "POST":
            # Default quantity to 1 for complex items
            borrow_request = BorrowRequest.objects.create(
                borrower=patron, 
                item=item, 
                quantity=1,  # Default quantity for complex items
                date=timezone.now()
            )
            borrow_request.save()
            send_message_to_librarians(
                subject=f"New Borrow Request: {patron.name} - {item.name}",
                content=f"{patron.name} has requested to borrow {item.name}.",
                link=reverse('borrow:approve_requests'),
                sender=patron
            )
            messages.success(request, 'Your borrow request has been sent to the librarian.', extra_tags='current-page')
            return redirect('borrow:detail', pk=pk)
        
        return render(request, 'borrow/borrow.html', {
            'item': item, 
            'is_simple_item': is_simple_item, 
            'is_complex_item': is_complex_item
        })


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
                success = False

                try:
                    # Try to get the item as a SimpleItem
                    simple_item = SimpleItem.objects.get(id=item.id)
                    success = borrow_request.borrower.borrow_simple_item(simple_item, borrow_request.quantity, simple_item.days_to_return)
                except SimpleItem.DoesNotExist:
                    # If it's not a SimpleItem, try ComplexItem
                    try:
                        complex_item = ComplexItem.objects.get(id=item.id)
                        success = borrow_request.borrower.borrow_complex_item(complex_item, complex_item.days_to_return)
                    except ComplexItem.DoesNotExist:
                        messages.error(request, f"Item {item.name} not found in either Simple or Complex categories.", extra_tags='current-page')
                        return redirect('borrow:approve_requests')
                
                if success:
                    # Mark the BorrowRequest as approved
                    borrow_request.status = BorrowRequest.APPROVED
                    borrow_request.save()

                    messages.success(request, f"Request for {borrow_request.quantity} of {item.name} has been approved.", extra_tags='current-page')
                else:
                    messages.error(request, f"Item borrowing failed for {borrow_request.item.name}. Please try again.", extra_tags='current-page')
            except Exception as e:
                messages.error(request, f"Error occurred while approving the request: {str(e)}", extra_tags='current-page')
                return redirect('borrow:approve_requests')
            
            borrow_request.approve()
            send_message(
                recipient=borrow_request.borrower,
                subject=f"Borrow Request Approved: {borrow_request.item.name}",
                content=f"Your request to borrow {borrow_request.item.name} has been approved.",
                sender=librarian
            )

        elif action == 'reject':
            borrow_request.status = BorrowRequest.REJECTED
            borrow_request.save()
            messages.error(request, f"Request for {borrow_request.item.name} has been rejected.", extra_tags='current-page')
            borrow_request.reject()
            send_message(
                recipient=borrow_request.borrower,
                subject=f"Borrow Request Rejected: {borrow_request.item.name}",
                content=f"Your request to borrow {borrow_request.item.name} has been rejected.",
                sender=librarian
            )

        return redirect('borrow:approve_requests')

    return render(request, 'borrow/approve.html', {'borrow_requests': borrow_requests})

@login_required
def add_item(request):
    # Only librarians can reach this
    try:
        Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot add items.")
    
    if request.method == 'POST':
        # Grab the selected category and item type from the form POST
        category = request.POST.get('category', Item.CATEGORY_OTHER)
        item_type = request.POST.get('item_type', 'complex')  # Default to complex (individual) items
        
        # Redirect to the appropriate form, appending query parameters
        if item_type == 'simple':
            return redirect(f"{reverse('borrow:add_simple_item')}?category={category}")
        else:
            return redirect(f"{reverse('borrow:add_complex_item')}?category={category}")
    
    # Render the chooser with both item type and category options
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
            return redirect('borrow:manage_items')
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
            return redirect('borrow:manage_items')
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
    
    my_collections = Collections.objects.filter(creator=creator).order_by("title")
    
    if is_librarian:
        available_collections = Collections.objects.all().order_by("title")
    else:
        available_collections = Collections.objects.filter(
            Q(is_collection_private=False) | Q(is_collection_private=True, allowed_users=creator)
        ).order_by("title").distinct()

    return render(request, 'borrow/manage_collections.html', {
        'my_collections': my_collections,
        'joined_collections': available_collections,
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
        coll = get_object_or_404(Collections, pk=pk)
    else:
        coll = get_object_or_404(Collections, pk=pk, creator=creator)

    if request.method == "POST":
        form = CollectionForm(request.POST, instance=coll,
                              librarian=librarian if is_librarian else creator,
                              is_librarian=is_librarian, editing=True)
        if form.is_valid():
            # compute newly‐added items only
            old_set = set(coll.items_list.all())
            new_set = set(form.cleaned_data['items_list']) - old_set
            errs = []
            for item in new_set:
                existing = Collections.objects.exclude(pk=coll.pk).filter(items_list=item)
                if coll.is_collection_private:
                    if existing.exists():
                        errs.append(
                            f"'{item.name}' is in other collection(s). "
                            "Remove it from all other collections before adding it to a private collection."
                        )
                else:
                    priv = existing.filter(is_collection_private=True).first()
                    if priv:
                        errs.append(
                            f"'{item.name}' is in private collection “{priv.title}”. "
                            "Remove it from that collection before adding it to a public collection."
                        )
            if errs:
                for e in errs:
                    messages.error(request, e, extra_tags='current-page')
            else:
                form.save()
                messages.success(request, f"Collection '{coll.title}' updated.", extra_tags='current-page')
                return redirect('borrow:manage_collections')
    else:
        form = CollectionForm(instance=coll,
                              librarian=librarian if is_librarian else creator,
                              is_librarian=is_librarian, editing=True)

    return render(request, "borrow/edit_collection.html", {
        "form": form,
        "collection": coll,
    })

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
        collection_title = collection.title
        collection.delete()
        messages.success(request, f"Collection '{collection_title}' deleted successfully.", extra_tags='current-page')
        return redirect("borrow:manage_collections")
    return redirect("borrow:manage_collections")


class CollectionDetailView(generic.DetailView):
    model = Collections
    template_name = "borrow/collection_detail.html"

    def dispatch(self, request, *args, **kwargs):
        collection = self.get_object()
        if collection.is_collection_private and not request.user.is_authenticated:
            return HttpResponseForbidden("You do not have permission to view this collection.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_visible_items(self):
        collection = self.get_object()
        user = self.request.user
        
        # Determine which items are visible to the user
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
                
        return visible_items
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get visible items based on permissions
        visible_items = self.get_visible_items()
        
        # Apply all filters
        # Category filtering
        current_category = self.request.GET.get('category', '')
        if current_category in dict(Item.CATEGORY_CHOICES):
            visible_items = visible_items.filter(category=current_category)
        
        # Search filtering
        q = self.request.GET.get("q", "").strip()
        if q:
            visible_items = visible_items.filter(
                Q(name__icontains=q) |
                Q(location__icontains=q) |
                Q(instructions__icontains=q)
            )
        
        # Item type filtering
        item_type = self.request.GET.get('item_type', '')
        if item_type == 'simple':
            # Filter for SimpleItems
            visible_items = visible_items.filter(simpleitem__isnull=False)
        elif item_type == 'complex':
            # Filter for ComplexItems
            visible_items = visible_items.filter(complexitem__isnull=False)
            
            # Add condition filtering for complex items
            condition = self.request.GET.get('condition', '')
            if condition:
                # Use complexitem__condition to filter by condition
                visible_items = visible_items.filter(complexitem__condition=condition)
        
        # Minimum quantity filtering
        min_quantity = self.request.GET.get('min_quantity', '')
        if min_quantity:
            try:
                min_quantity = int(min_quantity)
                visible_items = visible_items.filter(quantity__gte=min_quantity)
            except ValueError:
                pass
        
        # Add items to context
        context['visible_items'] = visible_items
        
        # Add all filter parameters to context
        context['q'] = q
        context['current_category'] = current_category
        context['item_type'] = item_type
        context['condition'] = self.request.GET.get('condition', '')
        context['min_quantity'] = min_quantity
        
        # Add choices to context
        context['CategoryChoices'] = Item.CATEGORY_CHOICES
        context['ConditionChoices'] = ComplexItem.CONDITION_CHOICES
        
        return context

@login_required
def add_review(request, pk):
    item = get_object_or_404(Item, pk=pk)
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        messages.error(request, "You need to be a patron to review items.", extra_tags='current-page')
        return redirect('borrow:detail', pk=pk)
    has_borrowed = BorrowedItem.objects.filter(
        borrower=patron,
        item=item
    ).exists()
    
    if not has_borrowed:
        messages.error(request, "You can only review items you have borrowed.", extra_tags='current-page')
        return redirect('borrow:detail', pk=pk)
    try:
        existing_review = Review.objects.get(reviewer=patron, item=item)
    except Review.DoesNotExist:
        existing_review = None
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.item = item
            review.reviewer = patron
            review.save()
            messages.success(request, 
                "Your review has been updated." if existing_review else "Your review has been added.", 
                extra_tags='current-page'
            )
            return redirect('borrow:detail', pk=pk)
    else:
        form = ReviewForm(instance=existing_review)
    
    return render(request, 'borrow/add_review.html', {
        'form': form,
        'item': item,
        'existing_review': existing_review,
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
    borrowed_item = get_object_or_404(BorrowedItem, id=borrowed_item_id)
    
    # Check if the user is the borrower or a librarian
    is_borrower = borrowed_item.borrower.user == request.user
    is_librarian = False
    try:
        Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        pass
    
    if not (is_borrower or is_librarian):
        return HttpResponseForbidden("You don't have permission to return this item.")
    
    item = borrowed_item.item
    item.quantity += borrowed_item.quantity
    item.save()
    
    borrowed_item.returned = True
    borrowed_item.save()
    
    messages.success(request, f"Item '{item.name}' has been returned successfully.", extra_tags='current-page')
    
    if is_borrower:
        return redirect('borrow:add_review', pk=item.id)
    
    # Otherwise redirect back to the appropriate page
    if is_librarian:
        return redirect('borrow:all_borrowed_items')
    else:
        return redirect('borrow:my_borrowed_items')

@login_required
def approve_collection_requests(request):
    try:
        librarian = Librarian.objects.get(user=request.user)
    except Librarian.DoesNotExist:
        return HttpResponseForbidden("You are not a librarian and cannot approve collection requests.")
    
    # Fetch all pending collection requests
    collection_requests = CollectionRequest.objects.filter(status=CollectionRequest.PENDING)
    
    if request.method == "POST":
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        
        try:
            collection_request = CollectionRequest.objects.get(id=request_id)
        except CollectionRequest.DoesNotExist:
            messages.error(request, "Request not found.", extra_tags='current-page')
            return redirect('borrow:approve_collection_requests')
        
        if action == 'approve':
            # Existing approval code
            collection_request.approve()
            collection = collection_request.collection
            user = collection_request.user
            collection.allowed_users.add(user)
            collection.save()
            
            # Send message to user
            send_message(
                recipient=collection_request.user,
                subject=f"Collection Request Approved: {collection_request.collection.title}",
                content=f"Your request to join the collection '{collection_request.collection.title}' has been approved. You now have access to it.",
                link=reverse('borrow:collection_detail', args=[collection_request.collection.id]),
                sender=librarian
            )
            
        elif action == 'reject':
            # Existing rejection code
            collection_request.reject()
            
            # Send message to user
            send_message(
                recipient=collection_request.user,
                subject=f"Collection Request Rejected: {collection_request.collection.title}",
                content=f"Your request to join the collection '{collection_request.collection.title}' has been rejected.",
                sender=librarian
            )
        
        return redirect('borrow:approve_collection_requests')
    
    return render(request, 'borrow/approve_collection_requests.html', {'collection_requests': collection_requests})

@login_required
def request_collection(request, pk):
    collection = get_object_or_404(Collections, pk=pk)
    
    if not collection.is_collection_private:
        messages.error(request, "This collection is already public and doesn't require access requests.", extra_tags='current-page')
        return redirect('borrow:collection_detail', pk=collection.id)
    
    try:
        patron = Patron.objects.get(user=request.user)
    except Patron.DoesNotExist:
        messages.error(request, "You need to be logged in to request collection access.", extra_tags='current-page')
        return redirect('borrow:collection_detail', pk=collection.id)
    
    # Check if the user already has access
    if collection.allowed_users.filter(pk=patron.pk).exists():
        messages.info(request, "You already have access to this collection.", extra_tags='current-page')
        return redirect('borrow:collection_detail', pk=collection.id)
    
    # Check if there's a pending request
    existing_request = CollectionRequest.objects.filter(
        user=patron,
        collection=collection,
        status=CollectionRequest.PENDING
    ).exists()
    
    if existing_request:
        messages.info(request, "You already have a pending request for this collection.", extra_tags='current-page')
        return redirect('borrow:collection_detail', pk=collection.id)
    
    if request.method == 'POST':
        form = CollectionRequestForm(request.POST)
        if form.is_valid():
            collection_request = CollectionRequest.objects.create(
                user=patron,
                collection=collection,
                date=timezone.now(),
                notes=form.cleaned_data['notes']
            )
            
            # Send message to librarians
            send_message_to_librarians(
                subject=f"Collection Access Request: {patron.name} - {collection.title}",
                content=f"{patron.name} has requested to join the collection '{collection.title}'.\n\nReason: {form.cleaned_data['notes']}",
                link=reverse('borrow:approve_collection_requests'),
                sender=patron
            )
            
            messages.success(request, "Your request to join this collection has been submitted.", extra_tags='current-page')
            return redirect('borrow:collection_detail', pk=collection.id)
    else:
        form = CollectionRequestForm()
    
    return render(request, 'borrow/request_collection.html', {'collection': collection, 'form': form})
    
@login_required
def create_collection(request):
    try:
        creator = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False
    
    if request.method == "POST":
        form = CollectionForm(request.POST, librarian=creator, is_librarian=is_librarian)
        if form.is_valid():
            new_items = list(form.cleaned_data['items_list'])
            errs = []
            for item in new_items:
                existing = Collections.objects.filter(items_list=item)
                if form.cleaned_data.get('is_collection_private'):
                    if existing.exists():
                        errs.append(f"'{item.name}' is already in '{existing.first().title}'; private collections must be disjoint.")
                else:
                    priv = existing.filter(is_collection_private=True).first()
                    if priv:
                        errs.append(f"'{item.name}' lives in private '{priv.title}'; public collections cannot include it.")
            
            if errs:
                for e in errs:
                    messages.error(request, e, extra_tags='current-page')
            else:
                coll = form.save(commit=False)
                if not is_librarian:
                    coll.is_collection_private = False
                coll.save()
                form.save_m2m()
                
                if coll.is_collection_private: 
                    # Get all users who are librarians
                    librarian_users = Librarian.objects.all()
                    # Add all librarian patrons to the collection's allowed_users
                    coll.allowed_users.add(*librarian_users)
                    coll.allowed_users.add(creator)
                else:
                    patron_users = Patron.objects.all()
                    coll.allowed_users.add(*patron_users)
                    coll.allowed_users.add(creator)
                    
                
                messages.success(request, f"Collection '{coll.title}' created.", extra_tags='current-page')
                return redirect('borrow:manage_collections')
    else:
        form = CollectionForm(librarian=creator, is_librarian=is_librarian)
    
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

@login_required
def delete_item(request, pk):
    try:
        librarian = Librarian.objects.get(user=request.user)
        is_librarian = True
    except Librarian.DoesNotExist:
        creator = Patron.objects.get(user=request.user)
        is_librarian = False
    
    if is_librarian:
        item = get_object_or_404(Item, pk=pk)
    else:
        item = get_object_or_404(Item, pk=pk, creator=creator)
    
    if request.method == "POST":
        item_name = item.name
        item.delete()
        messages.success(request, f"Item '{item_name}' deleted successfully.", extra_tags='current-page')
        return redirect("borrow:manage_items")
    return redirect("borrow:manage_items")

@login_required
def delete_review(request, review_id):
    """Delete a review if the user is the owner"""
    review = get_object_or_404(Review, pk=review_id)
    item_id = review.item.id
    
    if request.user != review.reviewer.user:
        messages.error(request, "You can only delete your own reviews.", extra_tags='current-page')
        return redirect('borrow:detail', pk=item_id)
    
    if request.method == "POST":
        review.delete()
        messages.success(request, "Your review has been deleted successfully.", extra_tags='current-page')
    
    return redirect('borrow:detail', pk=item_id)

@login_required
def message_list(request):
    try:
        patron = Patron.objects.get(user=request.user)
        messages = Message.objects.filter(recipient=patron)
        return render(request, 'borrow/messages.html', {'messages': messages})
    except Patron.DoesNotExist:
        messages.error(request, "You need to be a patron to access messages.", extra_tags='current-page')
        return redirect('home')

@login_required
def mark_message_read(request, message_id):
    try:
        patron = Patron.objects.get(user=request.user)
        message = get_object_or_404(Message, id=message_id, recipient=patron)
        
        if request.method == "POST":
            message.read = not message.read
            message.save()
            return redirect('borrow:messages')
        
        message.read = True
        message.save()
        
        if message.link and message.link.strip():
            return redirect(message.link)
        
        return redirect('borrow:messages')
    except Patron.DoesNotExist:
        messages.error(request, "You need to be a patron to access messages.", extra_tags='current-page')
        return redirect('home')

def unread_message_count(request):
    """API endpoint to get unread message count for AJAX calls"""
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    try:
        patron = Patron.objects.get(user=request.user)
        count = Message.objects.filter(recipient=patron, read=False).count()
        return JsonResponse({'count': count})
    except Patron.DoesNotExist:
        return JsonResponse({'count': 0})

def send_message(recipient, subject, content, link='', sender=None):
    """Helper function to send a message to a recipient"""
    Message.objects.create(
        recipient=recipient,
        subject=subject,
        content=content,
        link=link,
        sender=sender
    )

def send_message_to_librarians(subject, content, link='', sender=None):
    """Helper function to send a message to all librarians"""
    librarians = Librarian.objects.all()
    for librarian in librarians:
        Message.objects.create(
            recipient=librarian,
            subject=subject,
            content=content,
            link=link,
            sender=sender
        )
