from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, reverse
from borrow.models import Patron

class AdminRedirectMiddleware:
    """
    Middleware to handle admin users trying to access the main app
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff and not request.path.startswith('/admin/'):
            # Check if the current path is not a login/logout related path
            current_url = resolve(request.path)
            exempt_urls = [
                'account_logout', 
                'google_login', 
                'google_callback',
                'admin:logout'
            ]
            
            if current_url.url_name not in exempt_urls:
                # Check if the user is admin-only (has no associated Patron)
                try:
                    Patron.objects.get(user=request.user)
                    # User has Patron record, so proceed normally
                except Patron.DoesNotExist:
                    # User is admin-only, redirect to admin
                    messages.error(
                        request, 
                        "Admin accounts don't have access to the main app. Please log in with a normal account.",
                        extra_tags='admin-only'
                    )
                    return redirect('admin:index')

        return self.get_response(request)