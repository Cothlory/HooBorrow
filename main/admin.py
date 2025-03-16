from django.contrib import admin
from django.contrib.sites.models import Site
from django.contrib.sites.admin import SiteAdmin
from .models import RegisteredSite
from borrow.models import Patron, Librarian

# PatronAdmin: filter to only show Patrons who are not also Librarians
@admin.register(Patron)
class PatronAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'email', 'profile_photo')
    search_fields = ('name', 'email')
    list_filter = ('user',)

    def get_queryset(self, request):
        # Get the original queryset
        queryset = super().get_queryset(request)
        
        # Exclude users who are also librarians
        return queryset.exclude(user__in=Librarian.objects.values('user'))

# LibrarianAdmin: filter to only show Librarians and not Patrons who are not Librarians
@admin.register(Librarian)
class LibrarianAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'email', 'can_add_items')
    search_fields = ('name', 'email')
    list_filter = ('can_add_items',)

    def get_queryset(self, request):
        # Get the original queryset
        queryset = super().get_queryset(request)
        
        # Ensure we're only getting users who are librarians
        return queryset



