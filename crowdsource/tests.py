from crowdsource.models import ImageShare
from django.test import Client
from main.models import User
from django.test import TestCase
from django.urls import resolve, reverse
from unittest.mock import patch
from . import views


class TestCrowdsourceImageUrl(TestCase):

    def test_crowdsource_images_resloved(self):
        url = reverse('crowdsource')
        self.assertEqual(resolve(url).func, views.crowdsource_images)

    def test_crowdsource_delete_image_resloved(self):
        url = reverse('crowdsource.delete', args=[3])
        self.assertEqual(resolve(url).func, views.crowdsource_images_delete)

class TestImageShare(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestImageShare, cls).setUpClass()
        # USER
        cls.user = User.objects.create(
          full_name='user', email='user@example.com',
          password='secret', user_type='user', is_staff=False, active=True
        )

        # ADMIN
        cls.admin = User.objects.create(
          full_name='admin', email='admin@example.com',
          password='secret', user_type='admin', is_staff=True, active=True
        )

    def setUp(self):
        self.client = Client(HTTP_HOST='www.isac-simo.net')
        self.user = TestImageShare.user
        self.admin = TestImageShare.admin

    def test_image_share_creation(self):
        with patch.object(views, 'prune_old_image_share') as mock_prune_old_image_share:
            # Login as Normal user
            self.client.force_login(self.user)
            response = self.client.post('/crowdsource/images-share', {'object_type': 'wall', 'status': 'accepted', 'remarks': 'I am requesting images.'})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(ImageShare.objects.filter(object_type='wall', status='pending', user=self.user).exists())
            # Here, status should be pending (Only admin can change it to accepted or rejected)

            # Login as Admin
            self.client.force_login(self.admin)
            image_share = ImageShare.objects.filter(user=self.user).order_by('-created_at').first();
            response = self.client.post('/crowdsource/images-share', {'id': image_share.id, 'object_type': 'wall', 'status': 'accepted', 'remarks': 'I am requesting images.'})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(ImageShare.objects.filter(object_type='wall', status='accepted', user=self.user).exists())
            # Here, status should be accepted (As admin can change it to accepted or rejected)
        
        # Validate that Prune Old Image Share was called
        mock_prune_old_image_share.assert_called()

        # Downloading view called
        url = reverse('image_share_download', args=[image_share.id])
        self.assertEqual(resolve(url).func, views.image_share_download)