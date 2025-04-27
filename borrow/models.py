from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Item(models.Model):
    CATEGORY_BALLS   = 'BALLS'
    CATEGORY_STICKS  = 'STICKS'
    CATEGORY_NETS    = 'NETS'
    CATEGORY_OTHER   = 'OTHER'

    CATEGORY_CHOICES = [
        (CATEGORY_BALLS,  'Balls / Frisbees'),
        (CATEGORY_STICKS, 'Sticks / Rackets'),
        (CATEGORY_NETS,   'Nets / Goals'),
        (CATEGORY_OTHER,  'Other Sporting Equipment'),
    ]

    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    location = models.CharField(max_length=200)
    instructions = models.CharField(max_length=500)
    photo = models.ImageField(upload_to='item_photos/')
    
    # New fields for tracking original/copy relationship
    is_original = models.BooleanField(default=True)
    original_item = models.ForeignKey('self', on_delete=models.CASCADE, 
                                      null=True, blank=True, 
                                      related_name='copies')
    collection = models.ForeignKey('Collections', on_delete=models.SET_NULL, 
                                  null=True, blank=True, 
                                  related_name='collection_items')

    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
        help_text="Used for grouping in browse and picking the right form"
    )
    
    @property
    def is_in_private_collection(self):
        """Check if item is in a private collection"""
        return self.collection is not None and self.collection.is_collection_private
    
    @property
    def total_quantity(self):
        """Get total quantity across original and copies"""
        if self.is_original:
            copies_quantity = sum(copy.quantity for copy in self.copies.all())
            return self.quantity + copies_quantity
        return self.quantity

    def can_view(self, user):
        # Original items are always visible
        if self.is_original:
            return True
            
        # Items in collection need to check collection visibility
        if self.collection:
            if not self.collection.is_collection_private:
                return True
                
            if not user.is_authenticated:
                return False
                
            from .models import Librarian
            if Librarian.objects.filter(user=user).exists():
                return True
                
            # Check if user is allowed in this private collection
            return self.collection.allowed_users.filter(pk=user.patron.pk).exists()
            
        return True

    def __str__(self):
        status = "Original" if self.is_original else f"Copy in {self.collection.title if self.collection else 'No Collection'}"
        return f"{self.name} ({status}) - Qty: {self.quantity}"

    # Create a copy for collection
    def create_copy_for_collection(self, collection, quantity):
        """Create a copy of this item for a collection"""
        if self.quantity < quantity:
            raise ValueError(f"Not enough quantity. Available: {self.quantity}")
            
        # Create copy with same attributes
        copy_item = Item.objects.create(
            name=self.name,
            quantity=quantity,
            location=self.location,
            instructions=self.instructions,
            photo=self.photo,
            category=self.category,
            is_original=False,
            original_item=self,
            collection=collection
        )
        
        # Reduce quantity from original
        self.quantity -= quantity
        self.save()
        
        return copy_item


class SimpleItem(Item):
    
    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    def __str__(self):
        return self.name

class ComplexItem(Item):
    condition = models.CharField(max_length=200)

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers

    def __str__(self):
        return f"ComplexItem({self.name}, Condition: {self.condition})"


class Patron(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    
    def borrow_item(self, item, quantity=1, days_to_return=7):
        """Generic method to borrow any item"""
        if not item.can_view(self.user):
            return False
            
        if item.quantity < quantity:
            return False
            
        # Create borrowed record
        due_date = timezone.now() + timedelta(days=days_to_return)
        item_type = 'COMPLEX' if hasattr(item, 'condition') else 'SIMPLE'
        
        borrowed_item = BorrowedItem.objects.create(
            borrower=self,
            item=item,
            quantity=quantity,
            due_date=due_date,
            item_type=item_type
        )
        
        # Reduce item quantity
        item.quantity -= quantity
        item.save()
        
        return True
    
    def return_item(self, borrowed_item, quantity=None):
        """Generic method to return any borrowed item"""
        quantity_to_return = quantity or borrowed_item.quantity
        
        if quantity_to_return > borrowed_item.quantity:
            return False
            
        borrowed_item.return_item(quantity_to_return)
        return True
        
    # Legacy methods for backward compatibility
    def borrow_simple_item(self, simple_item, quantity=1, days_to_return=7):
        return self.borrow_item(simple_item, quantity, days_to_return)

    def borrow_complex_item(self, complex_item, days_to_return=7):
        return self.borrow_item(complex_item, 1, days_to_return)

    def return_simple_item(self, simple_item, quantity=1):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            item=simple_item,
            returned=False
        ).first()
        
        if not borrowed_item:
            return False
            
        return self.return_item(borrowed_item, quantity)

    def return_complex_item(self, complex_item, quantity=1):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            item=complex_item,
            returned=False
        ).first()
        
        if not borrowed_item:
            return False
            
        return self.return_item(borrowed_item, quantity)

    def __str__(self):
        return self.name


class BorrowedItem(models.Model):
    BORROWED_ITEM_TYPES = [
        ('SIMPLE', 'Simple Item'),
        ('COMPLEX', 'Complex Item'),
    ]
    
    borrower = models.ForeignKey(Patron, on_delete=models.CASCADE)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    due_date = models.DateTimeField()
    returned = models.BooleanField(default=False)
    item_type = models.CharField(max_length=7, choices=BORROWED_ITEM_TYPES)

    def __str__(self):
        item_name = self.item.name
        return f"{self.borrower.name} borrowed {self.quantity} of {item_name}"

    def is_late(self):
        if self.returned:
            return False
        return timezone.now() > self.due_date

    def return_item(self, quantity=None):
        """Return the borrowed item (or partial quantity)"""
        quantity_to_return = quantity or self.quantity
        
        if quantity_to_return > self.quantity:
            raise ValueError(f"Cannot return more than borrowed ({self.quantity})")
        
        # Add quantity back to the item
        self.item.quantity += quantity_to_return
        self.item.save()
        
        # Update the borrowed record
        self.quantity -= quantity_to_return
        if self.quantity <= 0:
            self.returned = True
            
        self.save()


class BorrowRequest(models.Model):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    borrower = models.ForeignKey(Patron, on_delete=models.CASCADE)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING
    )

    def __str__(self):
        return f"Request by {self.borrower.name} for {self.quantity} of {self.item.name} - {self.status}"

    def approve(self):
        self.status = self.APPROVED
        self.save()

    def reject(self):
        self.status = self.REJECTED
        self.save()

class Librarian(Patron):
    can_add_items = models.BooleanField(default=True)

    def add_item(self, item: Item):
        if self.can_add_items:
            item.save()
            print(f"Librarian {self.name} added item: {item.name}")
        else:
            print(f"{self.name} does not have permission to add items.")

    def delete_item(self, item: Item):
        item.delete()
        print(f"Librarian {self.name} deleted item: {item.name}")


class Collections(models.Model):
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    is_collection_private = models.BooleanField(default=False)
    creator = models.ForeignKey(Patron, on_delete=models.CASCADE, related_name='creator')
    allowed_users = models.ManyToManyField(
        Patron,
        blank=True,
        help_text="For private collections, only these patrons (librarians are automatically granted permission) can see and borrow items."
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @property
    def items_list(self):
        """Return all items in this collection"""
        return Item.objects.filter(collection=self, is_original=False)
    
    def add_item(self, original_item, quantity=1):
        """Add a copy of an item to the collection with specified quantity"""
        # Ensure the quantity is valid
        if quantity <= 0 or quantity > original_item.quantity:
            raise ValueError(f"Invalid quantity. Available: {original_item.quantity}")
            
        # Create a copy of the item for this collection
        copy = original_item.create_copy_for_collection(self, quantity)
        return copy
            
    def remove_item(self, copy_item):
        """Remove an item from this collection and return quantity to original"""
        if copy_item.collection != self or copy_item.is_original:
            raise ValueError("Item is not a copy in this collection")
            
        # Get the original and return quantity to it
        original = copy_item.original_item
        if original:
            original.quantity += copy_item.quantity
            original.save()
        
        # Store quantity for feedback message
        quantity = copy_item.quantity
        name = copy_item.name
        
        # Delete the copy
        copy_item.delete()
        
        return f"Returned {quantity} of {name} to original inventory"

    def can_view(self, user):
        if not self.is_collection_private:
            return True
            
        if not user.is_authenticated:
            return False
            
        from .models import Librarian
        try:
            if Librarian.objects.filter(user=user).exists():
                return True
                
            # Check if user is the creator
            if hasattr(user, 'patron') and self.creator == user.patron:
                return True
                
            # Check if user is in allowed_users
            if hasattr(user, 'patron') and self.allowed_users.filter(pk=user.patron.pk).exists():
                return True
        except:
            pass
            
        return False

    def __str__(self):
        return self.title

    def return_all_items(self):
        """Return all items in this collection to their original inventory"""
        returned_items = []
        
        for copy_item in self.collection_items.all():
            if copy_item.original_item and not copy_item.is_original:
                # Add quantity back to original
                original_item = copy_item.original_item
                original_item.quantity += copy_item.quantity
                original_item.save()
                
                returned_items.append({
                    'name': copy_item.name,
                    'quantity': copy_item.quantity
                })
                
                # Delete the copy item explicitly
                copy_item.delete()
    
        return returned_items


class CollectionRequest(models.Model): 
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]
    user = models.ForeignKey(Patron, on_delete=models.CASCADE)
    collection = models.ForeignKey(Collections, on_delete=models.CASCADE)
    date = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING
    )
    notes = models.CharField(max_length=500)

    def __str__(self):
        return f"Request by {self.user.name} for private collection {self.collection.name} - {self.status}"

    def approve(self):
        self.status = self.APPROVED
        self.save()

    def reject(self):
        self.status = self.REJECTED
        self.save()

class Review(models.Model):
    RATING_CHOICES = (
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    )
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(Patron, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('item', 'reviewer')
        
    def __str__(self):
        return f"{self.reviewer.name}'s review of {self.item.name}"

class CollectionItemAllocation(models.Model):
    collection = models.ForeignKey(Collections, on_delete=models.CASCADE, related_name='item_allocations')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='collection_allocations')
    allocated_quantity = models.IntegerField(default=1, 
        help_text="Number of units allocated to this collection")
    
    class Meta:
        unique_together = ('collection', 'item')
        
    def __str__(self):
        return f"{self.allocated_quantity} of {self.item.name} in {self.collection.title}"
