import os
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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

path_and_rename = PathAndRename("image")
path_and_rename_offline_models = PathAndRename("offline_models")
path_and_rename_object_types = PathAndRename("object_types")
path_and_rename_file_upload = PathAndRename("file")
path_and_rename_contributions = PathAndRename("contributions")

class Image(models.Model):
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(max_length=500, blank=True, null=True)
    user = models.ForeignKey("main.User", on_delete=models.SET_NULL, blank=True, null=True, related_name='user')
    lat = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)],max_length=100,null=True,blank=True)
    lng = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)],max_length=100,null=True,blank=True)
    project = models.ForeignKey(Projects, on_delete=models.SET_NULL, blank=True, null=True, related_name='project')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ImageFile(models.Model):
    image = models.ForeignKey(Image, related_name='image_files', on_delete=models.CASCADE)
    file = models.ImageField(upload_to=path_and_rename)
    tested = models.BooleanField(default=False)
    result = models.CharField(blank=True, null=True, max_length=500)
    score = models.FloatField(validators=[MinValueValidator(-1), MaxValueValidator(1)],max_length=10,null=True,blank=True)
    object_type = models.CharField(blank=True, null=True, max_length=500)
    retrained = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    pipeline_status = models.TextField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.file.url

class ObjectType(models.Model):
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey("main.User", related_name='object_types', on_delete=models.SET_NULL, blank=True, null=True)
    project = models.ForeignKey(Projects, related_name='object_types', on_delete=models.CASCADE, blank=True, null=True)
    image = models.ImageField(upload_to=path_and_rename_object_types, default='object_types/default.jpg', blank=True)
    instruction = models.TextField(max_length=500, blank=True, null=True)
    verified = models.BooleanField(default=False)
    wishlist = models.BooleanField(default=False) # Accept Contribution if project is marked public
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Classifier(models.Model):
    name = models.CharField(max_length=200)
    given_name = models.CharField(max_length=200, blank=True, null=True)
    classes = models.CharField(max_length=200, blank=True, null=True)
    project = models.ForeignKey(Projects, related_name='classifiers', on_delete=models.CASCADE, blank=True, null=True)
    object_type = models.ForeignKey(ObjectType, related_name='classifiers', on_delete=models.SET_NULL, blank=True, null=True)
    order = models.IntegerField("Order", default=0, blank=False, null=False)
    offline_model = models.ForeignKey('OfflineModel', on_delete=models.SET_NULL, related_name='classifiers', blank=True, null=True)
    is_object_detection = models.BooleanField(default=False)
    ibm_api_key = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey("main.User", related_name='classifiers', on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def project_ibm_api_key(self):
        if self.project and self.project.ibm_api_key:
            return self.project.ibm_api_key
        return False

    def best_ibm_api_key(self):
        if self.ibm_api_key:
            return self.ibm_api_key
        elif self.project and self.project.ibm_api_key:
            return self.project.ibm_api_key
        else:
            return str(settings.IBM_API_KEY)

    class Meta:
        ordering = ['order']  # order is the field holding the order

class OfflineModel(models.Model):
    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=200)
    model_format = models.CharField(max_length=50)
    file = models.FileField(upload_to=path_and_rename_offline_models)
    offline_model_labels = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey("main.User", related_name='offline_models', on_delete=models.SET_NULL, blank=True, null=True)
    preprocess = models.BooleanField(default=False)
    postprocess = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.name and self.model_format:
            return self.name + ' - ' + self.model_format
        else:
            return ''

    def isObjectDetect(self):
        return True if self.model_type == 'OBJECT_DETECT' else False

    def isClassifier(self):
        return True if self.model_type == 'CLASSIFIER' else False

    def filename(self):
        try:
            return self.file.url.replace('/media/offline_models/','')
        except Exception as e:
            return ''

# File Upload
class FileUpload(models.Model):
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to=path_and_rename_file_upload)
    created_by = models.ForeignKey("main.User", related_name='file_uploads', on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def filename(self):
        try:
            return self.file.url.replace('/media/file/','')
        except Exception as e:
            return 'INVALID'

    def filepath(self):
        try:
            path = os.environ.get('PROJECT_FOLDER','') + self.file.url
            if not os.path.exists(path):
                path = os.path.join('media/file/', self.file.url)
            return path
        except Exception as e:
            return self.filename()

# Contribution in Wishlisted Object Type
class Contribution(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=path_and_rename_contributions, blank=True, null=True)
    object_type = models.ForeignKey(ObjectType, related_name='contributions', on_delete=models.CASCADE)
    is_helpful = models.BooleanField(default=False)
    created_by = models.ForeignKey("main.User", related_name='contributions', on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title