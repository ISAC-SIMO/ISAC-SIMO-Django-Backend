import os
import uuid

from django.db import models
from django.utils.deconstruct import deconstructible

# from main.models import User
from api.models import path_and_rename_image_share
from projects.models import Projects
from django.utils.translation import gettext_lazy as _


@deconstructible
class PathAndRename(object):
    def __init__(self, sub_path):
        self.path = sub_path

    def __call__(self, instance, filename):
        ext = filename.split('.')[-1]
        filename = '{}.{}'.format(uuid.uuid4().hex, ext)
        return os.path.join(self.path, filename)


path_and_rename_crowdsource = PathAndRename("crowdsource")

IMAGE_TYPE = [
    ('raw', "Raw"),
    ('processed', "Processed")
]

IMAGE_SHARE_STATUS = [
    ('pending', "Pending"),
    ('accepted', "Accepted"),
    ('rejected', "Rejected")
]


# File Upload
class Crowdsource(models.Model):
    file = models.ImageField(_("File"), upload_to=path_and_rename_crowdsource)
    object_type = models.CharField(_("Object Type"), max_length=200, default='other')  # wall,rebar,door,brick etc.
    image_type = models.CharField(_("Image Type"), max_length=50, choices=IMAGE_TYPE, default='raw')  # raw or processed
    username = models.CharField(_("Username"), max_length=200, blank=True, null=True)
    created_by = models.ForeignKey("main.User", related_name='crowdsources', verbose_name=_("Crowdsources"),
                                   on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(_("created_at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated_at"), auto_now=True)

    def __str__(self):
        return self.file.url or 'N/A'

    def filename(self):
        try:
            return self.file.url.replace('/media/crowdsource/', '')
        except Exception as e:
            return 'INVALID'

    def bucket_key(self):
        try:
            return (self.object_type + '/' + self.file.url.replace('/media/crowdsource/', ''))
        except Exception as e:
            import time
            return ('error/' + str(int(time.time())))

    def filepath(self):
        try:
            path = os.environ.get('PROJECT_FOLDER', '') + self.file.url
            if not os.path.exists(path):
                path = os.path.join('media/crowdsource/', self.file.url)
            return path
        except Exception as e:
            return self.filename()


# ImageShare
class ImageShare(models.Model):
    user = models.ForeignKey("main.User", verbose_name=_("User"), on_delete=models.SET_NULL, blank=True, null=True,
                             related_name='image_share')
    object_type = models.CharField(_("Object Type"), max_length=255, blank=True, null=True)
    status = models.CharField(_("ImageShare Status"), max_length=20, choices=IMAGE_SHARE_STATUS, default='pending')
    remarks = models.CharField(_("Remarks"), max_length=250)
    created_at = models.DateTimeField(_("created_at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated_at"), auto_now=True)

    def __str__(self):
        return self.object_type
