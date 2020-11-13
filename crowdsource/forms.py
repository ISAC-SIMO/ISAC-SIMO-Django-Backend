from crowdsource.models import Crowdsource
from django import forms
from api.models import ObjectType
from django.core.cache import cache

class CrowdsourceForm(forms.ModelForm):
    file = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    class Meta:
        model = Crowdsource     
        fields = ('object_type', 'image_type', 'file', 'username')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CrowdsourceForm, self).__init__(*args, **kwargs)
        # CACHE HANDLE ALL OBJECT TYPE CHOICE
        OBJECT_TYPE = cache.get('all_object_type_choices')
        if not OBJECT_TYPE:
          OBJECT_TYPE = [
            ('other', 'Other')
          ]

          all_object_types = ObjectType.objects.order_by('name').values_list('name', flat=True).distinct()
          for o in all_object_types:
            OBJECT_TYPE.append((o, o.title()))
          cache.set('all_object_type_choices', OBJECT_TYPE)
          
        self.fields['file'].help_text = 'Only Upload Files of Chosen Object Type and Image Type.'
        self.fields['file'].label = 'Multiple Files'
        self.fields['object_type'].widget = forms.Select(choices=OBJECT_TYPE)
        self.fields['username'].widget = forms.HiddenInput()