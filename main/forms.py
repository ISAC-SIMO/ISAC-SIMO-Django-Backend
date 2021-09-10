from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import models
from django.forms.widgets import FileInput

from .models import USER_TYPE, BASIC_USER_TYPE, PROJECT_ADMIN_ADDABLE_USER_TYPE, User
from projects.models import Projects
from django.utils.translation import gettext_lazy as _

class LoginForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    email = forms.EmailField(error_messages={'unique': 'Email and Password did not match'})
    class Meta:
        model = User     
        fields = ('email', 'password')
        labels = {
            'email': _('Email'),
            'password': _('Password'),
        }

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)

class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    type = forms.ChoiceField(choices=BASIC_USER_TYPE, widget=forms.RadioSelect, initial = 'user')

    class Meta:
        model = User
        fields = ('email', 'full_name', 'image', 'password1', 'password2', 'type')
        labels = {
            'email':  _('Email'),
            'full_name': _('Full Name'),
            'image': _('Profile Picture'),
            'type': _('User Type'),
        }

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.fields['image'].required = False
        self.fields['full_name'].required = True
        self.fields['password1'].help_text = _('Use strong password with at least 8 characters.')
        self.fields['password2'].help_text = _('Enter the same password.')


class AdminRegisterForm(UserCreationForm):
    email = forms.EmailField()

    user_type = forms.ChoiceField(choices=USER_TYPE, widget=forms.Select, initial = 'user')

    class Meta:
        model = User
        fields = ('email', 'full_name', 'image', 'password1', 'password2', 'user_type', 'projects')
        labels = {
            'email':  _('Email'),
            'full_name':  _('Full Name'),
            'image':  _('Profile Picture'),
            'password1':  _('Password'),
            'password2':  _('Confirm Password'),
            'user_type':  _('User Type')
        }
        widgets = {
            'projects': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(AdminRegisterForm, self).__init__(*args, **kwargs)
        
        self.fields['image'].required = False
        self.fields['user_type'].help_text = 'Choose User Type Wisely'
        if self.request and self.request.user.user_type == 'project_admin':
            self.fields['projects'].queryset = Projects.objects.filter(users__id=self.request.user.id)
            self.fields['user_type'].choices = PROJECT_ADMIN_ADDABLE_USER_TYPE


class AdminEditForm(UserCreationForm):
    email = forms.EmailField()

    user_type = forms.ChoiceField(choices=USER_TYPE, widget=forms.Select, initial = 'False')

    class Meta:
        model = User
        fields = ('email', 'full_name', 'image', 'password1', 'password2', 'user_type', 'projects', 'active')
        labels = {
            'email':  _('Email'),
            'full_name':  _('Full Name'),
            'image':  _('Profile Picture'),
            'password1':  _('Password'),
            'password2':  _('Confirm Password'),
            'user_type':  _('User Type')
        }
        widgets = {
            'projects': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(AdminEditForm, self).__init__(*args, **kwargs)
        self.fields['image'].required = False
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        self.fields['user_type'].help_text =  _('Choose User Type Wisely)')
        self.fields['projects'].help_text = _('Assign to Multiple Projects (User can view or take action depending on the projects they are assigned on)')
        if self.instance and self.instance.user_type == 'admin': # If User Model being edited is Admin type
            self.fields['user_type'].help_text = _('Choose User Type Wisely (This user is currently admin)')
            self.fields['projects'].help_text = _('Admin user can manipulate any projects (but selecting these is useful for api)')
        if self.request and self.request.user.user_type == 'project_admin': # If Project Admin is Editing User
            self.fields['projects'].queryset = Projects.objects.filter(users__id=self.request.user.id)
            self.fields['user_type'].choices = PROJECT_ADMIN_ADDABLE_USER_TYPE
            if self.instance and self.instance.user_type == 'admin':
                del self.fields['active'] # Do Not Allow Project Admin to change active status of other Admin
            
            if self.instance and (self.instance.created_by != self.request.user and self.instance.id != self.request.user.id): 
                # User was not created by this project admin. Then, give no edit access for user details.
                # Only Allow changing Project links.
                self.initial['email'] = self.instance.get_hidden_email
                self.fields['email'].widget.attrs['readonly'] = True
                self.fields['full_name'].widget.attrs['readonly'] = True
                del self.fields['image']
                del self.fields['password1']
                del self.fields['password2']
                del self.fields['user_type']
                del self.fields['active']

class ProfileForm(UserCreationForm):
    email = forms.EmailField()
    image = forms.ImageField(label=_('Profile Image'),required=False,
                            error_messages ={'invalid':"Image files only"},
                            widget=FileInput)
    class Meta:
        model = User
        fields = ('email', 'full_name', 'image', 'password1', 'password2')
        labels = {
            'email':  _('Email'),
            'full_name':  _('Full Name'),
            'password1':  _('Password'),
            'password2':  _('Confirm Password'),
        }

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.fields['image'].required = False
        self.fields['image'].widget.attrs['accept'] = 'image/x-png,image/gif,image/jpeg'
        self.fields['image'].widget.attrs['onchange'] = 'showBlobImage(event)'
        self.fields['full_name'].required = True
        self.fields['password1'].required = False
        self.fields['password1'].help_text = ''
        self.fields['password1'].widget.attrs['placeholder'] = '*****'
        self.fields['password2'].required = False
        self.fields['password2'].help_text = _('Keep Password blank to not change it.')
        self.fields['password2'].widget.attrs['placeholder'] = '*****'
