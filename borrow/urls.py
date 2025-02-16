from django.urls import path

from . import views

app_name = "borrow"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"), # search bar and all the options 
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
]
