from django.contrib import admin
from django.contrib.sites.models import Site
from django.contrib.sites.admin import SiteAdmin
from .models import RegisteredSite

admin.site.unregister(Site)

class CustomSiteAdmin(SiteAdmin):
    list_display = ('id', 'name', 'domain')

admin.site.register(RegisteredSite, CustomSiteAdmin)
