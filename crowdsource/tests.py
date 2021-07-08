from django.test import TestCase
from django.urls import resolve, reverse
from . import views


class TestCrowdsourceImageUrl(TestCase):

    def test_crowdsource_images_resloved(self):
        url = reverse('crowdsource')
        self.assertEqual(resolve(url).func, views.crowdsource_images)

    def test_crowdsource_delete_image_resloved(self):
        url = reverse('crowdsource.delete', args=[3])
        self.assertEqual(resolve(url).func, views.crowdsource_images_delete)