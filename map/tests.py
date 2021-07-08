from django.test import TestCase
from django.urls import resolve, reverse
from . import views


class TestMapUrl(TestCase):

    def test_map_check_resloved(self):
        url = reverse('map.check')
        self.assertEqual(resolve(url).func, views.check)

    def test_map_fetch_resloved(self):
        url = reverse('map.fetch')
        self.assertEqual(resolve(url).func, views.fetch)

    def test_map_test_resloved(self):
        url = reverse('map.test')
        self.assertEqual(resolve(url).func, views.test)
