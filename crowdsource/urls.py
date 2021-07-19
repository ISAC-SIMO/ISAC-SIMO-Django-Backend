from django.urls import path
from . import views

urlpatterns = [
    # Image & Image Files
    path('image', views.crowdsource_images, name="crowdsource"),
    path('image/delete/<int:id>', views.crowdsource_images_delete, name="crowdsource.delete"),

    #Image Share
    path('images-share', views.images_share, name="images_share"),
    path('images-share/delete/<int:id>', views.images_share_delete, name="images_share_delete"),

    path('images-share/download/<int:id>', views.image_share_download, name="image_share_download"),
]