from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from django.http import HttpResponseRedirect

class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter to prevent direct access to AllAuth views"""
    
    def is_open_for_signup(self, request):
        """Only allow signup through social accounts"""
        return False
        
    def respond_user_inactive(self, request, user):
        return HttpResponseRedirect(reverse('home'))
        
    def respond_email_verification_sent(self, request, user):
        return HttpResponseRedirect(reverse('home'))

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter to customize Google login behavior"""
    
    def is_open_for_signup(self, request, sociallogin):
        """Allow signup through Google"""
        return True