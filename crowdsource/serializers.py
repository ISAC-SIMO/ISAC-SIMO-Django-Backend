from crowdsource.helpers import move_object, upload_object
from rest_framework import serializers
from api.serializers import UserMinimalSerializer
from .models import Crowdsource
import uuid

class CrowdsourceSerializer(serializers.ModelSerializer):
    created_by = UserMinimalSerializer(many=False, read_only=True)
    
    class Meta:
        model = Crowdsource
        fields = ('id','file','object_type','image_type','username','created_by','created_at','updated_at')
        read_only_fields = ('username','created_by','created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get("request")
        user = None
        if request and request.user and request.user.is_authenticated:
            user = request.user

        username = request.POST.get('username', None)
        if not username and user:
            username = user.full_name
        if not username:
            username = "Anonymous User - " + uuid.uuid4().hex[:6].upper()
        
        crowdsource = Crowdsource.objects.create(object_type=validated_data.get('object_type'),
                                    image_type=validated_data.get('image_type'),
                                    username=username,
                                    created_by=user,
                                    file=validated_data.get('file'))
        upload_object(crowdsource.bucket_key(), crowdsource.filepath())
        return crowdsource

    def update(self, instance, validated_data):
        request = self.context.get("request")
        old_object_key = instance.bucket_key()
        instance.username = request.POST.get('username', instance.username)
        if(validated_data.get('file')):
            instance.file.delete()
            instance.file = validated_data.get('file')
        instance.object_type = validated_data.get('object_type', instance.object_type)
        instance.image_type = validated_data.get('image_type', instance.image_type)
        instance.image_type = validated_data.get('image_type', instance.image_type)
        instance.save()

        if old_object_key != instance.bucket_key():
            move_object(instance.bucket_key(), old_object_key)
        return instance