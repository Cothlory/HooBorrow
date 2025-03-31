from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Item(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    location = models.CharField(max_length=200)
    instructions = models.CharField(max_length=500)
    photo = models.ImageField(upload_to='item_photos/')

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    @property
    def is_in_private_collection(self):
        return self.collections.filter(is_collection_private=True).exists()

    def can_view(self, user):
        """
        Returns True if:
         - the item is not in any private collection, or
         - the user is authenticated and either is a librarian
           or is allowed to see at least one private collection the item is in.
        """
        if not self.is_in_private_collection:
            return True

        if not user.is_authenticated:
            return False

        if hasattr(user, 'is_librarian') and user.is_librarian:
            return True

        return self.collections.filter(
            is_collection_private=True,
            allowed_users__pk=user.patron.pk
        ).exists()

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
    borrower = models.ForeignKey(Patron, on_delete=models.CASCADE)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateTimeField()


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
        help_text="For private collections, only these users (plus librarians) can see and borrow items."
    )

    def can_view(self, user):
        if not self.is_collection_private:
            return True
        if not user.is_authenticated:
            return False
        if hasattr(user, 'is_librarian') and user.is_librarian:
            return True
        return self.allowed_users.filter(pk=user.patron.pk).exists()

    def clean(self):
        if self.is_collection_private:
            librarian_creator = Librarian.objects.filter(pk=self.creator.pk).first()
            if not librarian_creator or not librarian_creator.can_add_items:
                raise ValidationError("Only librarians can create private collections.")
            
        if self.pk:
            for item in self.items_list.all():
                other_collections = Collections.objects.filter(items_list=item).exclude(pk=self.pk)
                if self.is_collection_private:
                    if other_collections.exists():
                        raise ValidationError(
                            f"Item '{item.name}' is already in another collection and cannot be added to a private collection."
                        )
                else:
                    if other_collections.filter(is_collection_private=True).exists():
                        raise ValidationError(
                            f"Item '{item.name}' is in a private collection and cannot be added to a public collection."
                        )
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
