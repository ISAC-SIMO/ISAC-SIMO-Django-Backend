from django.urls import path
from . import views

urlpatterns = [
    # Image & Image Files
    path('image', views.crowdsource_images, name="crowdsource"),
    path('image/delete/<int:id>', views.crowdsource_images_delete, name="crowdsource.delete"),
]