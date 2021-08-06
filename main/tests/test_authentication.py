from main.authorization import is_admin, is_guest, is_user
from django.contrib.messages.api import get_messages
from django.test.client import Client
from main.forms import LoginForm, RegisterForm
from main.models import User
from django.test import TestCase
from django.urls import reverse


class TestAuthentication(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='www.isac-simo.net')
        self.email="user@example.com"
        self.full_name="my name"
        self.user_type="user"
        self.password="test@1234" # Needs to be Strong else will fail with validation message

    def test_register_login_logout(self):
        # REGISTER
        response = self.client.get(reverse('register')) # Load Register Page
        self.assertIsInstance(response.context['form'], RegisterForm) # RegisterForm is sent in render
        self.assertTemplateUsed(response, 'auth/register.html') # Returns correct template
        self.assertContains(response, 'Registration Page') # Has certain text in rendered view

        response = self.client.post(reverse('register'), {
            'email': self.email, 'full_name': self.full_name, 'type': self.user_type,
            'password1': self.password, 'password2': self.password
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        # LOGIN
        response = self.client.get(reverse('login')) # Load Register Page
        self.assertIsInstance(response.context['form'], LoginForm) # LoginForm is sent in render
        self.assertTemplateUsed(response, 'auth/login.html') # Returns correct template
        self.assertContains(response, 'Log in') # Has certain text in rendered view

        response = self.client.post(reverse('login'), {"email": self.email, "password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))
        # Quickly test authorization helper
        user = response.wsgi_request.user
        self.assertEqual(is_user(user), True)
        self.assertEqual(is_admin(user), False)

        # LOGOUT
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertEqual(is_guest(response.wsgi_request.user), True)
    
    def test_register_duplicate_email(self):
        User.objects.create_user(email=self.email, user_type=self.user_type, password=self.password)
        response = self.client.post(reverse('register'), {
            'email': self.email, 'full_name': self.full_name, 'type': self.user_type,
            'password1': self.password, 'password2': self.password
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User with this Email already exists')
    
    def test_register_project_admin_inactive_by_default(self):
        response = self.client.post(reverse('register'), {
            'email': self.email, 'full_name': self.full_name, 'type': 'project_admin',
            'password1': self.password, 'password2': self.password
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertEqual([msg.tags for msg in get_messages(response.wsgi_request)][0], 'info') # message.info is attached
        self.assertEqual(User.objects.filter(user_type='project_admin', email=self.email, active=False).count(), 1) # Users model has Active = False