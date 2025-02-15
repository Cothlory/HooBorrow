from django.db import models
from django.utils import timezone
from datetime import timedelta


class ItemCategory(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    instructions = models.CharField(max_length=500)

    def list_borrowers(self):
        borrowed_items = BorrowedItem.objects.filter(category=self)
        borrowers = [borrowed_item.borrower for borrowed_item in borrowed_items]
        return borrowers
    
    def __str__(self):
        return self.name

class Borrower(models.Model):
    name = models.CharField(max_length=200)
    computing_id = models.CharField(max_length=200)

    def borrow_category(self, category, quantity, days_to_return=7):
        if category.quantity >= quantity: 
            due_date = timezone.now() + timedelta(days=days_to_return)
            borrowed_item = BorrowedItem.objects.create(
                borrower = self,
                category = category, 
                quantity = quantity,
                due_date = due_date
            )
            category.quantity -= quantity
            category.save()
            return True
        return False
    
    def return_category(self, category, quantity):
        borrowed_item = BorrowedItem.objects.filter(
            borrower=self,
            category=category
        ).first()

        if borrowed_item and borrowed_item.quantity >= quantity:
            borrowed_item.quantity -= quantity
            borrowed_item.save()

            # if the borrower returned all of the borrowed items, remove the record
            if borrowed_item.quantity == 0: 
                borrow_item.delete()
            
            category.quantity += quantity
            category.save()
            return True
        return False 
    
    def __str__(self):
        return self.name


class BorrowedItem(models.Model):
    borrower = models.ForeignKey(Borrower, on_delete=models.CASCADE)
    category = models.ForeignKey(ItemCategory, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    due_date = models.DateTimeField()
    returned = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.borrower.name} borrowed {self.quantity} of {self.category.name}"

    def is_late(self):
        if self.returned:
            return False
        return timezone.now() > self.due_date
    
    def return_item(self):
        self.returned = True
        self.save()
