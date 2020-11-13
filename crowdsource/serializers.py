from rest_framework import serializers
from api.serializers import UserMinimalSerializer
from .models import Crowdsource

class CrowdsourceSerializer(serializers.ModelSerializer):
    created_by = UserMinimalSerializer(many=False, read_only=True)
    
    class Meta:
        model = Crowdsource
        fields = ('id','file','object_type','image_type','username','created_by','created_at','updated_at')
        read_only_fields = ('username','created_by','created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None
        crowdsource = Crowdsource.objects.create(object_type=validated_data.get('object_type'),
                                    image_type=validated_data.get('image_type'),
                                    username=request.POST.get('username', user if user else ''),
                                    created_by=user,
                                    file=validated_data.get('file'))
        return crowdsource

    def update(self, instance, validated_data):
        request = self.context.get("request")
        instance.username = request.POST.get('username', instance.username)
        if(validated_data.get('file')):
            instance.file.delete()
        return super().update(instance, validated_data)