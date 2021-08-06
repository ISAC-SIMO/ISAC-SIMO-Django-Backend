from django.conf import settings
from django.contrib.messages.api import get_messages
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from crowdsource.models import Crowdsource, ImageShare
from django.test import Client
from main.models import User
from django.test import TestCase
from django.urls import resolve, reverse
from unittest.mock import patch
from unittest import skipUnless
from . import views
from django.core.paginator import Page
from crowdsource.forms import CrowdsourceForm, ImageShareForm
from crowdsource.helpers import delete_object, get_object, get_object_list, move_object, upload_object


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

        # ANOTHER WAY TO RUN or START PATCHER INSTEAD MANUALLY
        # self.patcher = patch('crowdsource.views.prune_old_image_share')
        # self.mock_prune_old_image_share = self.patcher.start()
        # self.addCleanup(self.patcher.stop)

    @patch('crowdsource.views.prune_old_image_share')
    def test_image_share_creation(self, mock_prune_old_image_share):
        # Login as Normal user
        self.client.force_login(self.user)
        response = self.client.post(reverse('images_share'), {'object_type': 'wall', 'status': 'accepted', 'remarks': 'I am requesting images.'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ImageShare.objects.filter(object_type='wall', status='pending', user=self.user).exists())
        # Here, status should be pending (Only admin can change it to accepted or rejected)

        # Login as Admin
        self.client.force_login(self.admin)
        image_share = ImageShare.objects.filter(user=self.user).order_by('-created_at').first();
        response = self.client.post(reverse('images_share'), {'id': image_share.id, 'object_type': 'wall', 'status': 'accepted', 'remarks': 'I am requesting images.'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ImageShare.objects.filter(object_type='wall', status='accepted', user=self.user).exists())
        # Here, status should be accepted (As admin can change it to accepted or rejected)

        # Validate that Prune Old Image Share was called
        mock_prune_old_image_share.assert_called()

        # Downloading view called
        url = reverse('image_share_download', args=[image_share.id])
        self.assertEqual(resolve(url).func, views.image_share_download)

        # Deleting Image Share Request
        response = self.client.post(reverse('images_share_delete', args=[image_share.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ImageShare.objects.filter(id=image_share.id).exists())

        # List Image Share Page
        response = self.client.get(reverse('images_share')+"?q=test") # Load Image Share List
        self.assertIsInstance(response.context['form'], ImageShareForm) # ImageShareForm is sent in render
        self.assertIsInstance(response.context['images_share'], Page) # Page (Paginator specific page) is sent in render
        self.assertEqual(response.context['query'], "test") # Query parameteter value (q) is sent back
        self.assertTemplateUsed(response, 'images_share.html') # Returns correct template
        self.assertContains(response, 'Image Share Request') # Has certain text in rendered view

class TestCrowdSource(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCrowdSource, cls).setUpClass()
        # USER
        cls.user = User.objects.create_user(
          full_name='user', email='user@example.com',
          password='secret', user_type='user', is_active=True
        )

        # ADMIN
        cls.admin = User.objects.create(
          full_name='admin', email='admin@example.com',
          password='secret', user_type='admin', is_staff=True, active=True
        )

    def setUp(self):
        self.client = Client(HTTP_HOST='www.isac-simo.net')
        self.user = TestCrowdSource.user
        self.admin = TestCrowdSource.admin

    @patch('django.db.models.fields.files.FieldFile.delete')
    @patch('django.db.models.fields.files.FieldFile.save')
    @patch('crowdsource.views.move_object')
    @patch('crowdsource.views.upload_object')
    @patch('crowdsource.views.delete_object')
    @patch('main.views.upload_object')
    def test_crowd_source_crud(self, mock_upload_object_while_loggin_in, mock_delete_object, mock_upload_object, mock_move_object, mock_save_image_file, mock_delete_image_file):
        with open(finders.find('dist/img/avatar.png'), 'rb') as image:
            # Guest User
            response = self.client.post(reverse('crowdsource'), {'object_type': 'wall', 'image_type': 'raw', 'file': image})
            self.assertEqual(response.status_code, 302)
            # print([msg.message for msg in get_messages(response.wsgi_request)]) # Sample: Get Message from response
            # print(Crowdsource.objects.values())
            self.assertTrue(Crowdsource.objects.filter(object_type='wall', image_type='raw').exists())
            mock_save_image_file.assert_called()

            # Session stores guest users crowdsource contributions (And if logged in, it is linked to them)
            session = self.client.session
            self.assertEqual(len(session["crowdsource_images"]), 1)

            # Manually Login User
            response = self.client.post(reverse('login'), {'email':'user@example.com', 'password':'secret'})
            # This should link current session crowdsource images to this user automatically.
            self.assertEqual(Crowdsource.objects.filter(created_by=self.user).count(), 1)
            mock_upload_object_while_loggin_in.assert_called()

            # Login as Admin
            self.client.force_login(self.admin)
            crowdsource = Crowdsource.objects.filter(object_type='wall', image_type='raw').order_by('-created_at').first()
            response = self.client.post(reverse('crowdsource'), {'id': crowdsource.id, 'object_type': 'facade', 'image_type': 'raw'})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(Crowdsource.objects.filter(object_type='facade', image_type='raw').exists())
            # Here, Admin user can update and make changes
            # Validate that move_object was called (because the object_type changes, thus folder in bucket must change)
            mock_move_object.assert_called()

            # Admin can also PERFORM DIRECT UPLOAD TO IBM COS BUCKET
            response = self.client.post(reverse('crowdsource'), {'object_type': 'test', 'image_type': 'raw', 'file': image, 'direct_upload': True})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Crowdsource.objects.count(), 1) # Do not add in database
            # Validate that upload_object was called
            mock_upload_object.assert_called()

            # Deleting Crowdsource Request
            response = self.client.post(reverse('crowdsource.delete', args=[crowdsource.id]))
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Crowdsource.objects.filter(id=crowdsource.id).exists())
            mock_delete_object.assert_called()
            mock_delete_image_file.assert_called()

        # List Crowdsource Page
        response = self.client.get(reverse('crowdsource')+"?q=test") # Load Crowdsource List
        self.assertIsInstance(response.context['form'], CrowdsourceForm) # CrowdsourceForm is sent in render
        self.assertIsInstance(response.context['crowdsources'], Page) # Page (Paginator specific page) is sent in render
        self.assertEqual(response.context['query'], "test") # Query parameteter value (q) is sent back
        self.assertEqual(response.context['dash'], "master/base.html") # base.html is dash context value (If logged in)
        self.assertTemplateUsed(response, 'crowdsource_images.html') # Returns correct template
        self.assertContains(response, 'Total Crowdsource Images: 0') # Has certain text in rendered view

@skipUnless(settings.PRODUCTION, "Ignore Test for Uploading Images to IBM COS")
class TestCrowdSourceImageUrl(TestCase):

    def test_ibm_cos_upload_move_delete_helper(self):
        # Upload a sample file
        image = SimpleUploadedFile("test.png", b"file_content", content_type="image/png")
        success = upload_object("test/test.png", image.open(), True)
        self.assertEqual(success, True)

        # Check if that file exists in COS
        file = get_object("test/test.png")
        self.assertNotEqual(file, False)
        self.assertEqual(file["ContentType"], "image/png")

        # Move that sample file
        success = move_object("test/test-moved.png", "test/test.png")
        self.assertEqual(success, True)

        # Check if that moved file exists in COS
        file = get_object("test/test-moved.png")
        self.assertNotEqual(file, False)

        # Check if that moved file does not exist in old path
        file = get_object("test/test.png")
        self.assertEqual(file, False)

        # get_object_list should return Array when length > 1 (at least this one)
        file_list = get_object_list("test")
        self.assertGreaterEqual(len(file_list), 1)

        # Delete that sample file
        success = delete_object("test/test-moved.png")
        self.assertEqual(success, True)

        # Check if that deleted file (moved location) does not exist anymore
        file = get_object("test/test-moved.png")
        self.assertEqual(file, False)


class TestCrowdsourceForm(TestCase):
    def test_crowd_source_form(self):
        f = open(finders.find('dist/img/avatar.png'), 'rb').read()
        upload_file = {
            "file": SimpleUploadedFile(name='avatar.png', content=f, content_type='image/png')
        }
        user = User.objects.create_user(
            full_name='user', email='user@example.com',
            password='secret', user_type='user', is_active=True
        )
        form_data = {
            "object_type": "test object",
            "image_type": "raw",
            "username": "admin",
            "created_by": user.id,

        }

        form = CrowdsourceForm(data=form_data, files=upload_file)
        self.assertTrue(form.is_valid())


class TestImageShareForm(TestCase):
    def test_image_share_form(self):
        user = User.objects.create_user(
            full_name='user', email='user@example.com',
            password='secret', user_type='user', is_active=True
        )
        form_data = {
            "object_type": "test object",
            "status": "pending",
            "remarks": "remark",
            "user": user.id,

        }

        form = ImageShareForm(data=form_data)
        self.assertTrue(form.is_valid())
