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
    quantity = models.IntegerField(default=1)
    location = models.CharField(max_length=200)
    instructions = models.CharField(max_length=500)
    photo = models.ImageField(upload_to='item_photos/')
    days_to_return = models.IntegerField(default=7)

    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
        help_text="Used for grouping in browse and picking the right form"
    )

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    @property
    def is_in_private_collection(self):
        return self.collections.filter(is_collection_private=True).exists()

    def can_view(self, user):
        if not self.is_in_private_collection:
            return True

        if not user.is_authenticated:
            return False

        from .models import Librarian
        if Librarian.objects.filter(user=user).exists():
            return True

        for col in self.collections.filter(is_collection_private=True):
            if col.can_view(user):
                return True
        return False

    def __str__(self):
        return self.name

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
    
    def borrow_simple_item(self, simple_item, quantity, days_to_return=7):
        if simple_item.quantity >= quantity: 
            due_date = timezone.now() + timedelta(days=days_to_return)
            borrowed_item = BorrowedItem.objects.create(
                borrower=self,
                item=simple_item, 
                quantity=quantity,
                due_date=due_date,
                item_type = 'SIMPLE'
            )
            simple_item.quantity -= quantity
            simple_item.save()
            return True
        return False

    def borrow_complex_item(self, complex_item, days_to_return=7):
        if complex_item.quantity >= 1:
            due_date = timezone.now() + timedelta(days=days_to_return)
            borrowed_item = BorrowedItem.objects.create(
                borrower=self,
                item=complex_item,
                quantity=1,
                due_date=due_date,
                item_type='COMPLEX'
            )
            complex_item.quantity -= 1
            complex_item.save()
            return True
        return False

    def return_simple_item(self, simple_item, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            item=simple_item
        ).first()

        if borrowed_item and borrowed_item.quantity >= quantity:
            borrowed_item.quantity -= quantity
            borrowed_item.save()

            if borrowed_item.quantity == 0:
                borrowed_item.delete()
            
            simple_item.quantity += quantity
            simple_item.save()
            return True
        return False

    def return_complex_item(self, complex_item, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            item=complex_item
        ).first()

        if borrowed_item and borrowed_item.quantity >= quantity:
            borrowed_item.quantity -= quantity
            borrowed_item.save()

            if borrowed_item.quantity == 0:
                borrowed_item.delete()
            
            complex_item.quantity += quantity
            complex_item.save()
            return True
        return False

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
        if self.item_type == 'SIMPLE':
            return f"{self.borrower.name} borrowed {self.quantity} of {self.item.simpleitem.name}"
        return f"{self.borrower.name} borrowed {self.quantity} of {self.item.complexitem.name}"

    def is_late(self):
        if self.returned:
            return False
        return timezone.now() > self.due_date

    def return_item(self):
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
    items_list = models.ManyToManyField(Item, blank=True, related_name="collections")
    is_collection_private = models.BooleanField(default=False)
    creator = models.ForeignKey(Patron, on_delete=models.CASCADE, related_name='creator')
    allowed_users = models.ManyToManyField(
        Patron,
        blank=True,
        help_text="For private collections, only these patrons (librarians are automatically granted permission) can see and borrow items."
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def can_view(self, user):
        if not self.is_collection_private:
            return True
        if not user.is_authenticated:
            return False
        from .models import Librarian
        if Librarian.objects.filter(user=user).exists():
            return True
        return self.allowed_users.filter(pk=user.patron.pk).exists()

    def clean(self):
        """
        Only validate *newly added* items against the private/public-collection rules.
        This lets you remove items freely even if they were previously in a private collection.
        """
        if not self.pk:
            return
        
        orig = Collections.objects.get(pk=self.pk)
        old_items = set(orig.items_list.all())
        new_items = set(self.items_list.all()) - old_items
        for item in new_items:
            qs = Collections.objects.filter(items_list=item)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            if self.is_collection_private:
                if qs.exists():
                    raise ValidationError(
                        f"Item '{item.name}' is already in another collection "
                        f"and cannot be added to a private collection."
                    )
            else:
                priv = qs.filter(is_collection_private=True).first()
                if priv:
                    raise ValidationError(
                        f"Item '{item.name}' is in private collection "
                        f"'{priv.title}' and cannot be added to this public collection."
                    )

        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

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
