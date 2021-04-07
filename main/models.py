import os
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils.deconstruct import deconstructible
from django.db.models import Q

from projects.models import Projects
from api.models import ObjectType
from django.utils.translation import gettext_lazy as _

USER_TYPE = [
    ('user', "User"),
    ('engineer', "Engineer"),
    ('government', "Government"),
    ('project_admin', "Project Admin"),
    ('admin', "Admin"),
]

BASIC_USER_TYPE = [
    ('user', "User"),
    ('project_admin', "Project Admin")
]

PROJECT_ADMIN_ADDABLE_USER_TYPE = [
    ('user', "User"),
    ('engineer', "Engineer"),
    ('project_admin', "Project Admin"),
]

@deconstructible
class PathAndRename(object):
    def __init__(self, sub_path):
        self.path = sub_path

    def __call__(self, instance, filename):
        ext = filename.split('.')[-1]
        filename = '{}.{}'.format(uuid.uuid4().hex, ext)
        return os.path.join(self.path, filename)

path_and_rename = PathAndRename("user_images")

class UserManager(BaseUserManager):
    def create_user(self, email,  password=None, user_type='user', is_active=True):
        if not email:
            raise ValueError(_("Users must have email address"))
        if not password:
            raise ValueError(_("Users must have password"))
        else:
            user_obj = self.model(
                email=self.normalize_email(email)
            )
            user_obj.set_password(password) #change password
            user_obj.user_type = user_type
            user_obj.active = is_active
            user_obj.save(using = self._db)
            return user_obj

    def create_staffuser(self, email, password=None):
        staff_user = self.create_user(
            email,
            password = password,
            user_type = 'user'
        )
        return staff_user

    def create_superuser(self, email, password=None):
        super_user = self.create_user(
            email,
            password = password,
            user_type = 'admin'
        )
        return super_user

class User(AbstractBaseUser):
    email = models.EmailField(_("Email"),max_length=255, unique=True)
    full_name = models.CharField(_("Full Name"), max_length=255, blank=True, null=True)
    active = models.BooleanField(_("Active"),default=True) #can login
    user_type = models.CharField(_("User Type"), max_length=50, choices=USER_TYPE, default='user')
    is_staff = models.BooleanField(_("Is Staff"), default=False)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add = True)
    image = models.ImageField(_("Image"), upload_to=path_and_rename, default='user_images/default.png', blank=True)
    projects = models.ManyToManyField('projects.Projects', verbose_name=_("Projects"), blank=True, related_name='users')
    # USER IS LINKED TO PROJECT WITH m2m AND USER CAN UPLOAD IMAGE FOR SPECIFIC PROJECT
    # AND VIEW THE IMAGES EITHER ADDED BY THIS USER -OR- BELONGS TO THIS USERS m2m PROJECTS

    USERNAME_FIELD='email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        str = self.full_name or ''
        if str:
            str = str + ' - '

        str = str + (self.email or '(no email)')
        return str
    
    def get_full_name(self):
        return self.full_name

    def get_project_list(self):
        if self.visible_projects:
            return "<br/> ".join(list(map(lambda x: '⮞ '+x.project_name, self.visible_projects)))
        else:
            return "<br/> ".join(list(map(lambda x: '⮞ '+x.project_name, self.projects.all())))
    
    def get_project_json(self, request):
        projects = []
        project_list = []
        if request and request.user and not request.user.is_anonymous and request.user.id:
            project_list = self.projects.all()
        else:
            project_list = Projects.objects.filter(guest=True)

        for project in project_list:
            projects = projects + [{
                'id': project.id,
                'project_name': project.project_name,
                'project_desc': project.project_desc
            }]
        return projects

    def get_object_detect_json(self, request):
        objects = []
        url = ""
        if request:
            url = request.scheme + '://' + request.META['HTTP_HOST']
        # TODO: probably in future we will not get all() objects below
        # We probably will get request.GET.get('project_id') which will be coming for each project specific mobile app
        # So we need to filter ObjectType with this project e.g. ObjectType.objects.filter(project=project_id).order_by('created_at').all()

        object_types = []
        # IF Logged in user return all linked Projects Object types
        if request and request.user and not request.user.is_anonymous and request.user.id:
            projects = Projects.objects.filter(users__id=request.user.id)
            object_types = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('name').all()
        # Else if Guest user return object type for projects marked as Guest=True
        else:
            projects = Projects.objects.filter(guest=True)
            object_types = ObjectType.objects.filter(Q(project__in=projects)).order_by('name').all()

        for o in object_types:
            image = None
            default_image = True
            if o.image:
                image = url + str(o.image.url)
                default_image =True if "default.jpg" in image else False

            objects = objects + [{
                'id': o.id,
                'name': o.name.title(),
                'instruction': o.instruction if o.instruction else "",
                'image': image,
                'default_image': default_image,
                'countries': list(map(lambda x: x.code, o.countries)),
                'verified': o.verified,
                'aspect': [2, 2],
                'project': o.project.project_name,
            }]
        return objects

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_admin(self):
        if self.user_type == 'admin':
            return True

    @property
    def is_project_admin(self):
        if self.user_type == 'project_admin':
            return True

    @property
    def is_engineer(self):
        if self.user_type == 'engineer':
            return True

    @property
    def is_government(self):
        if self.user_type == 'government':
            return True

    @property
    def is_user(self):
        if self.user_type == 'user':
            return True

    @property
    def is_active(self):
        return self.active
