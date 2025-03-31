from django import forms
from .models import SimpleItem, ComplexItem, Collections

class SimpleItemForm(forms.ModelForm):
    class Meta:
        model = SimpleItem
        fields = ['name', 'quantity', 'location', 'instructions', 'photo']

class ComplexItemForm(forms.ModelForm):
    class Meta:
        model = ComplexItem
        fields = ['name', 'quantity', 'location', 'instructions', 'condition', 'photo']

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
            if is_librarian:
                self.fields.pop('allowed_users')
            else:
                self.fields['is_collection_private'].widget = forms.HiddenInput()
                self.fields['is_collection_private'].initial = False
