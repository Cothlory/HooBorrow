from django.contrib import admin
from .models import Item, SimpleItem, ComplexItem

# Customizing the display of SimpleItem and ComplexItem under the Item admin
class ItemAdmin(admin.ModelAdmin):
    # Add fields for SimpleItem and ComplexItem
    list_display = ('name', 'quantity', 'location', 'instructions', 'item_type', 'get_condition', 'get_photos')

    search_fields = ('name', 'location')

    # Display condition only for ComplexItem
    def get_condition(self, obj):
        if isinstance(obj, ComplexItem):
            return obj.condition
        return "N/A"
    get_condition.short_description = 'Condition'

    # Display photos only for ComplexItem
    def get_photos(self, obj):
        if isinstance(obj, ComplexItem):
            return ", ".join([photo.image.url for photo in obj.photo.all()])
        elif isinstance(obj, SimpleItem):
            return obj.photo.image.url if obj.photo else "No photo"
        return "No photo"
    get_photos.short_description = 'Photos'

    # Determine the item type based on the model class
    def item_type(self, obj):
        if isinstance(obj, SimpleItem):
            return "Simple Item"
        elif isinstance(obj, ComplexItem):
            return "Complex Item"
        return "Item"
    item_type.short_description = 'Type'

    # Ensure SimpleItem and ComplexItem are separated properly
    def get_fieldsets(self, request, obj=None):
        if isinstance(obj, SimpleItem):
            return (
                (None, {
                    'fields': ('name', 'quantity', 'location', 'instructions', 'photo')
                }),
            )
        elif isinstance(obj, ComplexItem):
            return (
                (None, {
                    'fields': ('name', 'quantity', 'location', 'instructions', 'condition')
                }),
                ('Photos', {
                    'fields': ('photo',),
                    'classes': ('collapse',),
                }),
            )
        return super().get_fieldsets(request, obj)

# Register both SimpleItem and ComplexItem with the same admin model
class SimpleItemAdmin(ItemAdmin):
    # Ensure SimpleItem uses the ItemAdmin
    pass

class ComplexItemAdmin(ItemAdmin):
    # Ensure ComplexItem uses the ItemAdmin
    pass

# Registering the models with Django Admin
admin.site.register(SimpleItem, SimpleItemAdmin)
admin.site.register(ComplexItem, ComplexItemAdmin)
admin.site.register(Item)  # This registers the base model for reference
