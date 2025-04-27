from django import template

register = template.Library()

@register.filter
def can_view(item, user):
    return item.can_view(user)

@register.filter
def can_view_collection(collection, user):
    if collection is None:
        return False
    return collection.can_view(user)

@register.filter
def class_name(obj):
    """Returns the class name of an object"""
    return obj.__class__.__name__

@register.filter
def get_item_allocation(allocations, item):
    """Find and return item allocation for a given item"""
    for allocation in allocations:
        if allocation.item == item:
            return allocation
    return None
