from django import forms
from django.db import models
from django.forms.widgets import Input, Select, Textarea

from api.models import OfflineModel
from isac_simo.classifier_list import detect_object_model_id
from main.models import User

from .models import Projects
from django.utils.translation import gettext_lazy as _

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Projects     
        fields = ('project_name', 'project_desc', 'detect_model', 'ibm_service_url', 'ibm_api_key', 'offline_model', 'image', 'public')
        labels = {
            'project_name': _('Project Name'),
            'project_desc': _('Description'),
            'image': _("Project Image"),
            'detect_model': _("Online Object Detect Model"),
            'offline_model': _("Offline Object Detect Model"),
            'ibm_api_key': _("IBM API KEY"),
            'ibm_service_url': _("IBM Service URL"),
            'public': _('Is Publicly Visible')
        }
        widgets = {
          'project_desc': Textarea(attrs={'rows':4, 'cols':20}),
          'detect_model': Textarea(attrs={'rows':1, 'cols':20, 'placeholder':'Default: '+detect_object_model_id}),
          'ibm_api_key': Input(attrs={'placeholder':'Enter your IBM Watson API Key'}),
          'ibm_service_url': Input(attrs={'placeholder':'Enter a valid IBM Service URL'}),
          'offline_model': Select(attrs={'placeholder':'Select Offline Model'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        self.fields['detect_model'].help_text = 'Make sure the Objects for this model are created <a href="/app/watson/object/list">Here</a><br/>And add required Classifiers for those model <a href="/app/watson/classifier/create">Here</a>'
        self.fields['offline_model'].help_text = 'If Offline Object-Detect Model is provided it is given 1st priority over online model. <br/>Add Offline Model <a href="/app/offline_model/create">Here</a>'
        self.fields['offline_model'].queryset = OfflineModel.objects.filter(model_type='OBJECT_DETECT')
        self.fields['offline_model'].empty_label = ''
        self.fields['ibm_api_key'].help_text = 'If Provided this Project will be use given Watson Service.'
        self.fields['ibm_service_url'].initial = 'https://api.us-south.visual-recognition.watson.cloud.ibm.com'
        self.fields['public'].help_text = 'Choose if you want this Project to be Publicly Available to any user. Anyone can join the project or contribute.'
