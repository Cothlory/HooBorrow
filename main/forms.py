from allauth.account.forms import LoginForm as AllAuthLoginForm
from allauth.account.forms import SignupForm as AllAuthSignupForm
from allauth.account.forms import ResetPasswordForm as AllAuthResetPasswordForm
from django import forms

class CustomLoginForm(AllAuthLoginForm):
    login = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Username',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        })
    )
    remember = forms.BooleanField(required=False)
