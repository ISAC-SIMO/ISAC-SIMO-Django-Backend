import os
import uuid

from django.db import models
from django.utils.deconstruct import deconstructible

# from main.models import User
from projects.models import Projects

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

# File Upload
class Crowdsource(models.Model):
    file = models.ImageField(upload_to=path_and_rename_crowdsource)
    object_type = models.CharField(max_length=200, default='other') # wall,rebar,door,brick etc.
    image_type = models.CharField(max_length=50, choices=IMAGE_TYPE, default='raw') # raw or processed
    username = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey("main.User", related_name='crowdsources', on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or self.file.url

    def filename(self):
        try:
            return self.file.url.replace('/media/crowdsource/','')
        except Exception as e:
            return 'INVALID'

    def filepath(self):
        try:
            path = os.environ.get('PROJECT_FOLDER','') + self.file.url
            if not os.path.exists(path):
                path = os.path.join('media/crowdsource/', self.file.url)
            return path
        except Exception as e:
            return self.filename()