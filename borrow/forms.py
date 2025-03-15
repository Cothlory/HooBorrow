from django import forms
from .models import SimpleItem, ComplexItem

class SimpleItemForm(forms.ModelForm):
    class Meta:
        model = SimpleItem
        fields = ['name', 'quantity', 'location', 'instructions', 'photo']

class ComplexItemForm(forms.ModelForm):
    class Meta:
        model = ComplexItem
        fields = ['name', 'quantity', 'location', 'instructions', 'condition', 'photo']
