from projects.models import Projects
from django.test.utils import override_settings
from main.models import User
from django.test import TestCase
from rest_framework.test import APIClient
import tempfile

@override_settings(DEBUG=True)
class ProfileRoute(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ProfileRoute, cls).setUpClass()
        # USER
        cls.user = User.objects.create(
          full_name='user', email='user@example.com',
          password='secret', user_type='user', is_staff=False, active=True
        )

        # PROJECT
        cls.project = Projects.objects.create(
          id=1,
          project_name='First Global Project', image="image.jpg",
          project_desc='First Global Project Description', guest=True
        )
        cls.project_name_lower = 'first global project';

        # Assign User the Project
        cls.user.projects.add(cls.project)

    def setUp(self):
        self.client = APIClient(HTTP_HOST='www.isac-simo.net', ACCEPT='application/json')
        self.user = ProfileRoute.user
        self.project = ProfileRoute.project
        self.project_name_lower = ProfileRoute.project_name_lower

    def test_project_unique_name_property_must_be_correct(self):
        """
        The unique_name() property of project must be correct (unique)
        """
        self.assertEqual(self.project.unique_name(), (self.project_name_lower + '-' + str(self.project.id)))

    def test_profile_api_works_for_guest_users_as_expected(self):
        """
        The /api/profile API route must work for guest users (properly)
        """
        response = self.client.get(path='/api/profile/', content_type='application/json')
        # print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('projects')), 1) # Has One Project (as we setUp as Global Project)
        self.assertEqual(response.data.get('projects')[0].get('id'), 1) # First Project (id = 1)
        self.assertEqual(len(response.data.get('object_types')), 0) # Has NO Object Types
        self.assertEqual(response.data, {
          'id': 0, 'full_name': 'Guest', 'email': 'Guest', 'user_type': 'Guest', 'image': 'http://www.isac-simo.net/media/user_images/default.png',
          'projects': [
            {'id': 1, 'project_name': 'First Global Project', 'project_desc': 'First Global Project Description'}
          ],
          'object_types': []
        })

    def test_profile_api_works_for_logged_in_users_as_expected(self):
        """
        The /api/profile API route must work for logged in users / authenticated users (properly)
        """
        self.client.force_authenticate(user=self.user) # Authenticate the user
        response = self.client.get(path='/api/profile/', content_type='application/json')
        # print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('projects')), 1) # Has One Project (as we setUp as Global Project)
        self.assertEqual(response.data, {
          'id': 1, 'full_name': 'user', 'email': 'user@example.com', 'user_type': 'user', 'image': 'http://www.isac-simo.net/media/user_images/default.png',
          'projects': [
            {'id': 1, 'project_name': 'First Global Project', 'project_desc': 'First Global Project Description'}
          ],
          'object_types': []
        })

    def test_ping_route(self):
        """
        The /api/ping API route should pass
        """
        self.client.force_authenticate(user=None, token=None) # Logout the user
        response = self.client.get(path='/api/ping/', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get("ping"), "pong")