from django.db import models
from django.utils import timezone
from datetime import timedelta

# For storing photos of complex items
class Photo(models.Model):
    image = models.ImageField(upload_to='item_photos/')
    description = models.CharField(max_length=500)

class Item(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    location = models.CharField(max_length=200)
    instructions = models.CharField(max_length=500)

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers

    def __str__(self):
        return self.name

class SimpleItem(Item):
    photo = models.OneToOneField(Photo, on_delete=models.CASCADE)
    
    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    def __str__(self):
        return self.name

class ComplexItem(Item):
    condition = models.CharField(max_length=200)
    photo = models.ManyToManyField(Photo)  # Multiple photos for complex items

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers

    def __str__(self):
        return f"ComplexItem({self.name}, Condition: {self.condition})"


class Patron(models.Model):
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    def borrow_simple_item(self, item, quantity, days_to_return=7):
        if item.quantity >= quantity: 
            due_date = timezone.now() + timedelta(days=days_to_return)
            borrowed_item = BorrowedItem.objects.create(
                borrower=self,
                simple_item=item, 
                quantity=quantity,
                due_date=due_date
            )
            item.quantity -= quantity
            item.save()
            return True
        return False

    def borrow_complex_item(self, complex_item, days_to_return=7):
        if complex_item.quantity >= 1:
            due_date = timezone.now() + timedelta(days=days_to_return)
            borrowed_item = BorrowedItem.objects.create(
                borrower=self,
                complex_item=complex_item,
                quantity=1,
                due_date=due_date
            )
            complex_item.quantity -= 1
            complex_item.save()
            return True
        return False

    def return_simple_item(self, simpleItem, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            simple_item=simple_item
        ).first()

        if borrowed_item and borrowed_item.quantity >= quantity:
            borrowed_item.quantity -= quantity
            borrowed_item.save()

            if borrowed_item.quantity == 0:
                borrowed_item.delete()
            
            category.quantity += quantity
            category.save()
            return True
        return False

    def return_complex_item(self, complex_item, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            complex_item=complex_item
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


