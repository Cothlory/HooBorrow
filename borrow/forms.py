from django import forms
from .models import SimpleItem, ComplexItem, Collections

class SimpleItemForm(forms.ModelForm):
    class Meta:
        model = SimpleItem
        fields = ['name', 'quantity', 'location', 'instructions', 'photo', 'category']

class ComplexItemForm(forms.ModelForm):
    class Meta:
        model = ComplexItem
        fields = ['name', 'quantity', 'location', 'instructions', 'condition', 'photo', 'category']

class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Quantity", required=True)

class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collections
        fields = ['title', 'description', 'items_list', 'is_collection_private', 'allowed_users']
        widgets = {
            'items_list': forms.CheckboxSelectMultiple,
            'allowed_users': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, librarian=None, is_librarian=True, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        if librarian and not self.instance.pk:
            self.instance.creator = librarian

        if editing:
            if 'is_collection_private' in self.fields:
                self.fields.pop('is_collection_private')
            if not self.instance.is_collection_private and 'allowed_users' in self.fields:
                self.fields.pop('allowed_users')
        else:
            if not is_librarian:
                self.fields['is_collection_private'].widget = forms.HiddenInput()
                self.fields['is_collection_private'].initial = False

    def clean(self):
        """Validate many-to-many relationships on creation and editing.
           This ensures:
             - For a private collection: an item cannot be in any other collection.
             - For a public collection: an item already in a private collection cannot be added.
        """
        cleaned_data = super().clean()
        items = cleaned_data.get("items_list")
        is_private = cleaned_data.get("is_collection_private", self.instance.is_collection_private)
        if items:
            for item in items:
                qs = Collections.objects.filter(items_list=item)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if is_private:
                    if qs.exists():
                        raise forms.ValidationError(
                            f"Item '{item.name}' is already in another collection and cannot be added to a private collection."
                        )
                else:
                    if qs.filter(is_collection_private=True).exists():
                        raise forms.ValidationError(
                            f"Item '{item.name}' is in a private collection and cannot be added to a public collection."
                        )
        return cleaned_data

class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Quantity", required=True)
