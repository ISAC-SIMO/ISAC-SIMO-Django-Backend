from django.test import TestCase
from django.contrib.staticfiles import finders
from api.models import Image, ImageFile
from main.models import User


class TestImageFileTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="testuser@example.com", user_type="user", password="test@1234")
        image = Image.objects.create(title="test title", description="test desc", user=user, lat=26, lng=84)
        file = finders.find('dist/img/avatar.png')
        ImageFile.objects.create(image=image, file=file)

    def test_image_created(self):
        self.assertEqual(Image.objects.count(), 1)

    def test_image_file_created(self):
        self.assertEqual(ImageFile.objects.count(), 1)
