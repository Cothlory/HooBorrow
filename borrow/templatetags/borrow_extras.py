from django import template

register = template.Library()

@register.filter
def can_view(item, user):
    return item.can_view(user)

@register.filter
def can_view_collection(collection, user):
    return collection.can_view(user)
