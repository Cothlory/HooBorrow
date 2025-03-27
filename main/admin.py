from django.contrib import admin
from django.contrib.sites.models import Site
from django.contrib.sites.admin import SiteAdmin
from .models import RegisteredSite
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from borrow.models import Patron, Librarian
from django.contrib import messages
from django.db import transaction

# PatronAdmin: filter to only show Patrons who are not also Librarians
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
class LibrarianAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'email', 'can_add_items')
    search_fields = ('name', 'email')
    list_filter = ('can_add_items',)

    def get_queryset(self, request):
        # Get the original queryset
        queryset = super().get_queryset(request)
        
        # Ensure we're only getting users who are librarians
        return queryset

def assign_librarian(modeladmin, request, queryset):
    with transaction.atomic():
        for user in queryset:
            try:
                # # Get patron data if it exists
                Patron.objects.filter(user=user).delete()
                
                Librarian.objects.create(
                    user=user,
                    name=user.get_full_name(),
                    email=user.email
                )
                messages.success(request, f"Librarian role assigned to {user.email}.")

            except Exception as e:
                messages.error(request, f"Error assigning librarian role to {user.email}: {str(e)}")

        
def assign_patron(modeladmin, request, queryset):
    for user in queryset:
        try:
            # Delete existing Librarian and Patron roles
            Librarian.objects.filter(user=user).delete()
            Patron.objects.filter(user=user).delete()
            
            # Create a new Patron role
            Patron.objects.create(user=user, name=user.get_full_name(), email=user.email)

            messages.success(request, f"Patron role assigned to {user.email}.")
        except Exception as e:
            messages.error(request, f"Error assigning patron role to {user.email}: {str(e)}")

# Customize the UserAdmin to add custom actions
class CustomUserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "is_staff", "get_role")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name", "username")

    actions = [assign_librarian, assign_patron]  # Add custom actions to the admin

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "password1", "password2"),
        }),
    )

    # Display user role dynamically
    def get_role(self, obj):
        if Librarian.objects.filter(user=obj).exists():
            return "Librarian"
        elif Patron.objects.filter(user=obj).exists():
            return "Patron"
        return "Unknown"

    get_role.short_description = "Role"

# Unregister the default User admin and register the custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Patron)
admin.site.register(Librarian)

