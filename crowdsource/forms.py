from django.forms.widgets import Textarea
from crowdsource.models import Crowdsource, ImageShare
from django import forms
from api.models import ObjectType
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

def get_object_types():
    OBJECT_TYPE = cache.get('all_object_type_choices')
    if not OBJECT_TYPE:
        OBJECT_TYPE = [
            ('other', 'Other')
        ]

        all_object_types = ObjectType.objects.order_by('name').values_list('name', flat=True).distinct()
        for o in all_object_types:
            OBJECT_TYPE.append((o, o.title()))
        cache.set('all_object_type_choices', OBJECT_TYPE, 3600)
    return OBJECT_TYPE

class CrowdsourceForm(forms.ModelForm):
    file = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    class Meta:
        model = Crowdsource
        fields = ('object_type', 'image_type', 'file', 'username')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CrowdsourceForm, self).__init__(*args, **kwargs)
        # CACHE HANDLE ALL OBJECT TYPE CHOICE
        OBJECT_TYPE = get_object_types()

        self.fields['file'].help_text = _('Please, Only Upload Files of Chosen Object Type and Image Type.')
        self.fields['file'].label = _('Multiple Files')
        self.fields['object_type'].widget = forms.Select(choices=OBJECT_TYPE)
        self.fields['username'].widget = forms.HiddenInput()

        # ADMIN feature to directly upload to IBM COS
        if self.request and self.request.user.is_authenticated and self.request.user.user_type == 'admin':
            self.fields['direct_upload'] = forms.BooleanField(required=False, label="Direct Upload to Bucket without storing in Database & locally")

class ImageShareForm(forms.ModelForm):
    class Meta:
        model = ImageShare
        fields = ('object_type', 'status', 'remarks')
        widgets = {
          'remarks': Textarea(attrs={'rows':4, 'cols':20})
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(ImageShareForm, self).__init__(*args, **kwargs)
        # CACHE HANDLE ALL OBJECT TYPE CHOICE
        OBJECT_TYPE = get_object_types()
        self.fields['object_type'].widget = forms.Select(choices=OBJECT_TYPE)
        self.fields['object_type'].required = True
        if self.request and self.request.user.is_authenticated and self.request.user.user_type == 'admin':
            self.fields['status'].label = "Status"
        else:
            del self.fields['status'] # Allow only Admin to change status