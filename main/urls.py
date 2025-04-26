from django.urls import path, re_path
from . import views
from allauth.socialaccount.providers.google.views import oauth2_login, oauth2_callback

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    
    # Allow Google OAuth2 endpoints only
    path('google/login/', oauth2_login, name='google_login'),
    path('google/login/callback/', oauth2_callback, name='google_callback'),
    
    # Redirect all other AllAuth URLs to home
    re_path(r'^login/?$', views.redirect_to_home),
    re_path(r'^signup/?$', views.redirect_to_home),
    re_path(r'^password/set/?.*$', views.redirect_to_home),
    re_path(r'^password/reset/?.*$', views.redirect_to_home),
    re_path(r'^password/change/?$', views.redirect_to_home),
    re_path(r'^email/?$', views.redirect_to_home),
    re_path(r'^confirm-email/?.*$', views.redirect_to_home),
    re_path(r'^3rdparty/.*$', views.redirect_to_home),
    re_path(r'^social/.*$', views.redirect_to_home),
    
    # Special case for logout to avoid CSRF issues
    path('logout/', views.redirect_to_home),
]
