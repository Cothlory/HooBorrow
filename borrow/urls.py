from django.urls import path

from . import views

app_name = "borrow"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"), # search bar and all the options 
    path("item/<int:pk>/", views.DetailView.as_view(), name="detail"),
    path('collection/<int:pk>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    path('add_item/', views.add_item, name='add_item'),
    path('add_simple_item/', views.add_simple_item, name='add_simple_item'),
    path('add_complex_item/', views.add_complex_item, name='add_complex_item'),
    path('approve_requests/', views.approve_requests, name='approve_requests'),
    path('borrow/<int:pk>/', views.borrow_item, name='borrow_item'),
    path('manage_users/', views.manage_users, name='manage_users'),
    path('manage_collections/', views.manage_collections, name='manage_collections'),
    path('create_collection/', views.create_collection, name='create_collection'),
    path('manage_collections/edit/<int:pk>/', views.edit_collection, name='edit_collection'),
    path('manage_collections/delete/<int:pk>/', views.delete_collection, name='delete_collection'),
    path("<int:pk>/review/", views.add_review, name="add_review"),
    path("review/<int:review_id>/delete/", views.delete_review, name="delete_review"),
    path('my_borrowed_items/', views.my_borrowed_items, name='my_borrowed_items'),
    path('all_borrowed_items/', views.all_borrowed_items, name='all_borrowed_items'),
    path('return_item/<int:borrowed_item_id>/', views.return_item, name='return_item'),
    path('request_collection/<int:pk>/', views.request_collection, name='request_collection'),
    path('approve_collection_requests/', views.approve_collection_requests, name='approve_collection_requests'),
    path('manage_items/', views.manage_items, name='manage_items'),
    path('manage_items/edit/<int:pk>/', views.edit_item, name='edit_item'),
    path('manage_items/delete/<int:pk>/', views.delete_item, name='delete_item'),
    path('messages/', views.message_list, name='messages'),
    path('messages/<int:message_id>/read/', views.mark_message_read, name='mark_message_read'),
    path('messages/unread-count/', views.unread_message_count, name='unread_message_count'),
]
