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
