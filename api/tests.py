from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from main.models import User


class UserAccountAPITest(APITestCase):

    def setUp(self):
        User.objects.create_user(email="testuser@gmail.com", user_type="user", password="test@1234")

    def test_get_token(self):
        response = self.client.post(reverse('auth'), {"email": "testuser@gmail.com", "password": "test@1234"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token(self):
        user = self.client.post(reverse('auth'), {"email": "testuser@gmail.com", "password": "test@1234"})
        refresh_token = user.data["refresh"]
        response = self.client.post(reverse('auth_refresh'), {"refresh": refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)