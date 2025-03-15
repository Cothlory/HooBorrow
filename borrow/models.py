from django.db import models
from django.utils import timezone
from datetime import timedelta

# For storing photos of complex items
class Photo(models.Model):
    image = models.ImageField(upload_to='item_photos/')
    description = models.CharField(max_length=500)

class SimpleItem(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    instructions = models.CharField(max_length=500)
    location = models.CharField(max_length=200)

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(category=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    def __str__(self):
        return self.name

class ComplexItem(models.Model):
    name = models.CharField(max_length=200)
    condition = models.CharField(max_length=200)
    photos = models.ManyToManyField(Photo)  # Multiple photos for complex items
    quantity = models.IntegerField(default=0)
    location = models.CharField(max_length=200)

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(complex_item=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers

    def __str__(self):
        return f"ComplexItem({self.name}, Condition: {self.condition})"


class Patron(models.Model):
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)

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

    def return_category(self, category, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            simple_item=category
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
    borrower = models.ForeignKey(Patron, on_delete=models.CASCADE)
    simple_item = models.ForeignKey(SimpleItem, null=True, blank=True, on_delete=models.CASCADE)
    complex_item = models.ForeignKey(ComplexItem, null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    due_date = models.DateTimeField()
    returned = models.BooleanField(default=False)

    def __str__(self):
        if self.simple_item:
            return f"{self.borrower.name} borrowed {self.quantity} of {self.simple_item.name}"
        return f"{self.borrower.name} borrowed {self.quantity} of {self.complex_item.name}"

    def is_late(self):
        if self.returned:
            return False
        return timezone.now() > self.due_date
    
    def return_item(self):
        self.returned = True
        self.save()


class Librarian(Patron):
    def add_item(self, simple_item=None, complex_item=None):
        if simple_item:
            simple_item.save()
            print(f"Librarian added simple item category: {simple_item.name}")
        if complex_item:
            complex_item.save()
            print(f"Librarian added complex item: {complex_item.name}")


