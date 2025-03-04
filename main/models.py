from django.db import models
from django.contrib.sites.models import Site

# Create your models here.

class RegisteredSite(Site):
    class Meta:
        proxy = True
        ordering = ['id']
