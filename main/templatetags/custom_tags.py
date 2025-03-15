
from django import template
from borrow.models import Librarian  # import your Librarian model

register = template.Library()

@register.filter
def is_librarian(user):
    try:
        Librarian.objects.get(user=user)  # Check if the user is a librarian
        return True
    except Librarian.DoesNotExist:
        return False
