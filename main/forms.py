from allauth.account.forms import LoginForm as AllAuthLoginForm
from django import forms

class CustomLoginForm(AllAuthLoginForm):
  login = forms.CharField(widget=forms.TextInput(attrs={
    'placeholder': 'Username',
    'autocomplete': 'username',
    'id': 'id_login',
    'class': 'form-control'
  }))
  password = forms.CharField(widget=forms.PasswordInput(attrs={
    'placeholder': 'Password',
    'autocomplete': 'current-password',
    'id': 'id_password',
    'class': 'form-control'
  }))
  remember = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
    'id': 'id_remember',
    'class': 'form-check-input'
  }))
