from django.urls import path
from allauth.account.views import LoginView, LogoutView, SignupView
from . import views

urlpatterns = [
    path('accounts/signup/', SignupView.as_view(), name='account_signup'),
    path('accounts/role-select/', views.role_select, name='role_select'),
    path('accounts/login/', LoginView.as_view(), name='account_login'),
    path('accounts/logout/', LogoutView.as_view(), name='account_logout'),
    path('accounts/profile/', views.profile_view, name='profile'),
]
