from django.urls import path

from . import views

app_name = "borrow"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"), # search bar and all the options 
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    path('add_item/', views.add_item, name='add_item'),
    path('add_simple_item/', views.add_simple_item, name='add_simple_item'),
    path('add_complex_item/', views.add_complex_item, name='add_complex_item'),
]
