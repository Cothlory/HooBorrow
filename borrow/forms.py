from django import forms
from .models import SimpleItem, ComplexItem, Collections, Patron, Review

class SimpleItemForm(forms.ModelForm):
    class Meta:
        model = SimpleItem
        fields = ['name', 'quantity', 'location', 'instructions', 'photo', 'category']
        widgets = {
            'category': forms.HiddenInput(),
        }

class ComplexItemForm(forms.ModelForm):
    class Meta:
        model = ComplexItem
        fields = ['name', 'quantity', 'location', 'instructions', 'photo', 'condition', 'category']
        widgets = {
            'category': forms.HiddenInput(),
        }
class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Quantity", required=True)

class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collections
        fields = ['title', 'description', 'items_list', 'is_collection_private', 'allowed_users']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'items_list': forms.CheckboxSelectMultiple(),
            'is_collection_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allowed_users': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, librarian=None, is_librarian=True, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        if librarian and not self.instance.pk:
            self.instance.creator = librarian
        if editing:
            if 'is_collection_private' in self.fields:
                self.fields.pop('is_collection_private')
            if self.instance.is_collection_private:
                self.fields['allowed_users'].queryset = Patron.objects.all()
            else:
                if 'allowed_users' in self.fields:
                    self.fields.pop('allowed_users')
        else:
            if not is_librarian:
                if 'allowed_users' in self.fields:
                    self.fields.pop('allowed_users')
            else:
                self.fields['allowed_users'].queryset = Patron.objects.all()

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class CollectionRequestForm(forms.Form):
    notes = forms.CharField(label="Enter Reason", max_length=100)
