from datetime import timedelta
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import SimpleItem, ComplexItem, Patron, BorrowedItem, Librarian

# Patch the 'photo' field storage on our models to use FileSystemStorage in tests.
fs = FileSystemStorage(location='/tmp/django_test_media')
SimpleItem._meta.get_field('photo').storage = fs
ComplexItem._meta.get_field('photo').storage = fs

@override_settings(
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
    MEDIA_ROOT='/tmp/django_test_media',
    MEDIA_URL='/media/'
)
class ItemModelTests(TestCase):
    def setUp(self):
        self.image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        self.simple_item = SimpleItem.objects.create(
            name="Soccer Ball",
            quantity=10,
            location="Gym",
            instructions="Kick it well",
            photo=self.image,
        )
        self.complex_item = ComplexItem.objects.create(
            name="High-tech Drone",
            quantity=5,
            location="Storage",
            instructions="Handle with care",
            condition="New",
            photo=self.image,
        )

    # Tests that the string representation of a simple item returns its name.
    def test_simple_item_str(self):
        self.assertEqual(str(self.simple_item), "Soccer Ball")

    # Tests that the string representation of a complex item returns the expected format.
    def test_complex_item_str(self):
        expected = "ComplexItem(High-tech Drone, Condition: New)"
        self.assertEqual(str(self.complex_item), expected)

    # Tests that list_borrowers returns an empty list when no borrowers exist.
    def test_list_borrowers_empty(self):
        self.assertEqual(self.simple_item.list_borrowers(), [])
        self.assertEqual(self.complex_item.list_borrowers(), [])

@override_settings(
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
    MEDIA_ROOT='/tmp/django_test_media',
    MEDIA_URL='/media/'
)
class PatronBorrowReturnTests(TestCase):
    def setUp(self):
        self.image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.patron = Patron.objects.create(
            user=self.user,
            name="Test Patron",
            email="test@example.com"
        )
        self.simple_item = SimpleItem.objects.create(
            name="Basketball",
            quantity=5,
            location="Court",
            instructions="Bounce it",
            photo=self.image,
        )
        self.complex_item = ComplexItem.objects.create(
            name="VR Headset",
            quantity=3,
            location="Store",
            instructions="Wear it",
            condition="Good",
            photo=self.image,
        )

    # Tests that borrowing a simple item succeeds, decreases its quantity, and creates a BorrowedItem.
    def test_borrow_simple_item_success(self):
        success = self.patron.borrow_simple_item(self.simple_item, quantity=2, days_to_return=7)
        self.assertTrue(success)
        self.simple_item.refresh_from_db()
        self.assertEqual(self.simple_item.quantity, 3)
        borrowed = BorrowedItem.objects.filter(borrower=self.patron, item=self.simple_item).first()
        self.assertIsNotNone(borrowed)
        self.assertEqual(borrowed.quantity, 2)

    # Tests that borrowing a simple item fails when requesting more than is available.
    def test_borrow_simple_item_failure(self):
        success = self.patron.borrow_simple_item(self.simple_item, quantity=10)
        self.assertFalse(success)

    # Tests that returning a simple item updates the quantity and adjusts or removes the BorrowedItem.
    def test_return_simple_item(self):
        self.patron.borrow_simple_item(self.simple_item, quantity=3)
        success = self.patron.return_simple_item(self.simple_item, quantity=2)
        self.assertTrue(success)
        self.simple_item.refresh_from_db()
        self.assertEqual(self.simple_item.quantity, 4)
        borrowed = BorrowedItem.objects.filter(borrower=self.patron, item=self.simple_item).first()
        if borrowed:
            self.assertEqual(borrowed.quantity, 1)
        else:
            self.assertIsNone(borrowed)

    # Tests that borrowing a complex item succeeds, decreases its quantity, and creates a BorrowedItem.
    def test_borrow_complex_item_success(self):
        success = self.patron.borrow_complex_item(self.complex_item, days_to_return=7)
        self.assertTrue(success)
        self.complex_item.refresh_from_db()
        self.assertEqual(self.complex_item.quantity, 2)
        borrowed = BorrowedItem.objects.filter(borrower=self.patron, item=self.complex_item).first()
        self.assertIsNotNone(borrowed)
        self.assertEqual(borrowed.quantity, 1)

    # Tests that returning a complex item restores its quantity and removes the BorrowedItem if quantity reaches zero.
    def test_return_complex_item(self):
        self.patron.borrow_complex_item(self.complex_item)
        success = self.patron.return_complex_item(self.complex_item, quantity=1)
        self.assertTrue(success)
        self.complex_item.refresh_from_db()
        self.assertEqual(self.complex_item.quantity, 3)
        borrowed = BorrowedItem.objects.filter(borrower=self.patron, item=self.complex_item).first()
        self.assertIsNone(borrowed)

@override_settings(
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
    MEDIA_ROOT='/tmp/django_test_media',
    MEDIA_URL='/media/'
)
class BorrowedItemTests(TestCase):
    def setUp(self):
        self.image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        self.user = User.objects.create_user(username="lateuser", password="password")
        self.patron = Patron.objects.create(
            user=self.user,
            name="Late Patron",
            email="late@example.com"
        )
        self.simple_item = SimpleItem.objects.create(
            name="Tennis Racket",
            quantity=4,
            location="Court",
            instructions="Swing it",
            photo=self.image,
        )
        past_date = timezone.now() - timedelta(days=1)
        self.borrowed = BorrowedItem.objects.create(
            borrower=self.patron,
            item=self.simple_item,
            quantity=1,
            due_date=past_date,
            item_type="SIMPLE"
        )

    # Tests that is_late returns True when the due date is past and returns False after the item is marked as returned.
    def test_is_late(self):
        self.assertTrue(self.borrowed.is_late())
        self.borrowed.return_item()
        self.assertFalse(self.borrowed.is_late())

@override_settings(
    DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage',
    MEDIA_ROOT='/tmp/django_test_media',
    MEDIA_URL='/media/'
)
class ViewTests(TestCase):
    def setUp(self):
        self.image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        self.simple_item = SimpleItem.objects.create(
            name="Ping Pong",
            quantity=10,
            location="Club",
            instructions="Play it",
            photo=self.image,
        )

    # Tests that the index view returns a 200 status, uses the correct template, and displays the item name.
    def test_index_view(self):
        url = reverse('borrow:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'borrow/index.html')
        self.assertContains(response, "Ping Pong")

    # Tests that the detail view returns a 200 status, uses the correct template, and displays the item name.
    def test_detail_view(self):
        url = reverse('borrow:detail', kwargs={'pk': self.simple_item.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'borrow/detail.html')
        self.assertContains(response, "Ping Pong")
