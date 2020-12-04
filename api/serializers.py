import json
import os
from django.http.response import JsonResponse
import filetype
import cv2
import uuid
from django.conf import settings
from django.http import HttpResponse
from PIL import Image as PILImage
from rest_framework import serializers
from rest_framework.response import Response
from api.helpers import create_classifier, test_image

from main.models import User

from .models import Classifier, Contribution, FileUpload, Image, ImageFile, ObjectType, OfflineModel
from projects.models import Projects

class ProjectMinimalSerializer(serializers.ModelSerializer):
    unique_name = serializers.SerializerMethodField()

    def get_unique_name(self, obj):
        return obj.unique_name()

    class Meta:
        model = Projects
        fields = ('id','project_name','image','unique_name')

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    projects = ProjectMinimalSerializer(read_only=True, many=True)
    class Meta:
        model = User
        fields = ('id','email','password','full_name','user_type','image','projects')
        read_only_fields = ['id']

    def create(self, validated_data):
        user = User.objects.create(email=validated_data['email'],
                                full_name=validated_data['full_name'])
        if(validated_data.get('image')):
            user.image = validated_data.get('image')
        user.set_password(validated_data['password'])
        request = self.context.get("request")
        if request.POST.get('user_type'):
            user_type = request.POST.get('user_type')
            if request.user.is_admin and user_type in ['user','engineer','government','project_admin','admin']:
                user.user_type = user_type
            elif request.user.is_project_admin and user_type in ['user','engineer','project_admin']:
                user.user_type = user_type
            elif user_type == 'project_admin':
                user.user_type = user_type
                user.active = False
        user.save()
        return user

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if(validated_data.get('image')):
            if(instance.image != 'user_images/default.png'):
                instance.image.delete()
            instance.image = validated_data.get('image')
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.email = validated_data.get('email', instance.email)
        if(validated_data.get('password')):
            instance.set_password(validated_data['password'])
        if request.POST.get('user_type'):
            user_type = request.POST.get('user_type')
            if request.user.is_admin and user_type in ['user','engineer','government','project_admin','admin']:
                instance.user_type = user_type
            elif request.user.is_project_admin and user_type in ['user','engineer','project_admin']:
                instance.user_type = user_type
            elif user_type == 'project_admin':
                instance.user_type = user_type
                instance.active = False
        instance.save()
        return instance

class ImageFileSerializer(serializers.ModelSerializer):
    pipeline_status = serializers.SerializerMethodField()

    def get_pipeline_status(self, obj):
        try:
            return json.loads(obj.pipeline_status)
        except:
            return {}

    class Meta:
        model = ImageFile
        fields = ('id','file','tested','result','score','object_type','verified','pipeline_status','created_at')

class ImageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField(read_only=True)
    user_type = serializers.SerializerMethodField(read_only=True)
    project_name = serializers.SerializerMethodField(read_only=True)
    image_files = ImageFileSerializer(many=True, read_only=True)
    
    class Meta:
        model = Image
        fields = ('id','url','title','description','lat','lng','user_id','user_name','user_type','project_id','project_name','image_files','created_at','updated_at')
        read_only_fields = ('user_name','user_type','created_at', 'updated_at','project_name')

    def get_user_name(self, image):
        return image.user.full_name if image.user else None
    
    def get_user_type(self, image):
        return image.user.user_type if image.user else None
    
    def get_project_name(self, image):
        return image.project.project_name if image.project else None

    def create(self, validated_data):
        user = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
        image_files = self.context.get('view').request.FILES

        if len(image_files) > 0 and len(image_files) < 8: # Images count 1 to 7
            image = Image.objects.create(title=validated_data.get('title'),
                                        description=validated_data.get('description'),
                                        lat=validated_data.get('lat'),
                                        lng=validated_data.get('lng'),
                                        user_id=(user.id if user else None),
                                        project_id=request.POST.get('project_id', None))
            
            project = None
            object_type = None
            force_object_type = None
            # First check if object_type_id is provided
            if request.POST.get('object_type_id', None):
                object_type = ObjectType.objects.filter(id=request.POST.get('object_type_id')).get()
                if object_type:
                    project = object_type.project
                    force_object_type = object_type.name.lower()
            # Else check project_id
            elif request.POST.get('project_id', None):
                project = Projects.objects.filter(id=request.POST.get('project_id')).get()
            
            if not project and not object_type:
                image.delete()
                error = {'message': 'Neither Project nor Object Type Were Valid'}
                raise serializers.ValidationError(error)

            offline = False
            detect_model = project.detect_model

            try:
                if project.offline_model and project.offline_model.file:
                    offline = True
                    detect_model = project.offline_model
            except:
                offline = False

            e = 0 # Check if files uploaded or Not
            u = 0 # Uploaded Count
            for image_file in image_files.values():
                try:
                    img = PILImage.open(image_file)
                    img.verify()
                    image_obj = ImageFile.objects.create(image=image, file=image_file)

                    ################
                    ### RUN TEST ###
                    ################
                    test_image(image_obj, validated_data.get('title'), validated_data.get('description'), detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key)

                    u = u + 1
                except Exception as err:
                    print(err)
                    print('File Failed to Upload - NOT AN IMAGE')
                    e = e + 1
            
            if(u >= 1): # At least one uploaded good to go
                ###############################
                ##### IF FINE TO CONTINUE #####
                ###############################
                return image
            else: # No Files Upload Throw error
                image.delete()
                error = {'message': str(e)+' Files failed to Upload. (Probably, Files are not type Image)'}
                raise serializers.ValidationError(error)
        else:
            error = {'message': 'No Images provided or too much (>7) images provided.'}
            raise serializers.ValidationError(error)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.lat = validated_data.get('lat', instance.lat)
        instance.lng = validated_data.get('lng', instance.lng)
        instance.project_id = request.POST.get('project_id', None)

        # VERIFY ImageFiles Model from API checkmark array
        if request.POST.get('verified', False):
            verified_list = []
            if type(request.POST.get('verified', [])) == list:
                verified_list = request.POST.get('verified', [])
            else:
                verified_list = json.loads(request.POST.get('verified', '[]'))

            for image_file in instance.image_files.all():
                if image_file.id in verified_list:
                    image_file.verified = True
                else:
                    image_file.verified = False
                image_file.save()
        
        image_files = self.context.get('view').request.FILES

        project = None
        object_type = None
        force_object_type = None
        # First check if object_type_id is provided
        if request.POST.get('object_type_id', None):
            object_type = ObjectType.objects.filter(id=request.POST.get('object_type_id')).get()
            if object_type:
                project = object_type.project
                force_object_type = object_type.name.lower()
        # Else check project_id
        elif request.POST.get('project_id', None):
            project = Projects.objects.filter(id=request.POST.get('project_id')).get()
        
        if not project and not object_type:
            instance.delete()
            error = {'message': 'Neither Project nor Object Type Were Valid'}
            raise serializers.ValidationError(error)
        
        if len(image_files) < 8:
            e = 0 # Check if files uploaded or Not
            u = 0 # Uploaded Count
            for image_file in image_files.values():
                try:
                    img = PILImage.open(image_file)
                    img.verify()
                    image_obj = ImageFile.objects.create(image=instance, file=image_file)
                    offline = False
                    detect_model = project.detect_model

                    try:
                        if project.offline_model and project.offline_model.file:
                            offline = True
                            detect_model = project.offline_model
                    except:
                        offline = False
                    
                    ################
                    ### RUN TEST ###
                    ################
                    test_image(image_obj, validated_data.get('title'), validated_data.get('description'), detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key)
                    u = u + 1
                except Exception as err:
                    print(err)
                    print('File Failed to Upload - NOT AN IMAGE')
                    e = e + 1
            
            if(u >= 1): # At least one uploaded good to go
                instance.save()
                return instance
            else: # No Files Upload Throw error
                instance.save()
                return instance
                # error = {'message': str(e)+' Files failed to Upload. (Probably, Files are not type Image)'}
                # raise serializers.ValidationError(error)
        else:
            error = {'message': 'Too much (>7) images provided.'}
            raise serializers.ValidationError(error)

###################################
# CREATE AND STORE VIDEO TO FRAMES:
###################################
class VideoFrameSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField(read_only=True)
    user_type = serializers.SerializerMethodField(read_only=True)
    project_name = serializers.SerializerMethodField(read_only=True)
    image_files = ImageFileSerializer(many=True, read_only=True)
    
    class Meta:
        model = Image
        fields = ('id','url','title','description','lat','lng','user_id','user_name','user_type','project_id','project_name','image_files','created_at','updated_at')
        read_only_fields = ('user_name','user_type','created_at', 'updated_at', 'project_name')

    def get_user_name(self, image):
        return image.user.full_name if image.user else None
    
    def get_user_type(self, image):
        return image.user.user_type if image.user else None

    def get_project_name(self, image):
        return image.project.project_name if image.project else None

    # Function to get the frame image, save to image_file model and test it via ai model
    def getFrame(self, vidcap, count, sec, image_model, project=None, force_object_type=None):
        vidcap.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
        hasFrames,image = vidcap.read()
        if hasFrames:
            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
            saveto = os.path.join('media/image/', filename)
            saveto = None
            if not os.path.exists(os.path.join('media/image/')):
                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/image/'+filename
            else:
                saveto = os.path.join('media/image/', filename)

            cv2.imwrite(saveto, image) # save frame as JPG file
            image_obj = ImageFile.objects.create(image=image_model, file=str(os.path.join('media/image/', filename)).replace('media/',''))
            offline = False
            detect_model = project.detect_model

            try:
                if project.offline_model and project.offline_model.file:
                    offline = True
                    detect_model = project.offline_model
            except:
                offline = False
            
            ################
            ### RUN TEST ###
            ################
            test = test_image(image_obj, image_model.title, image_model.description, detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key)
        return hasFrames

    def create(self, validated_data):
        user = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
        video_files = self.context.get('view').request.FILES

        # If videos exists on upload store Image model to db
        if len(video_files) > 0 and len(video_files) < 8: # Video count 1 to 7
            image = Image.objects.create(title=validated_data.get('title'),
                                        description=(validated_data.get('description')+' - (Via Video Upload)'),
                                        lat=validated_data.get('lat'),
                                        lng=validated_data.get('lng'),
                                        user_id=(user.id if user else None),
                                        project_id=request.POST.get('project_id', None))

            project = None
            object_type = None
            force_object_type = None
            # First check if object_type_id is provided
            if request.POST.get('object_type_id', None):
                object_type = ObjectType.objects.filter(id=request.POST.get('object_type_id')).get()
                if object_type:
                    project = object_type.project
                    force_object_type = object_type.name.lower()
            # Else check project_id
            elif request.POST.get('project_id', None):
                project = Projects.objects.filter(id=request.POST.get('project_id')).get()
            
            if not project and not object_type:
                image.delete()
                error = {'message': 'Neither Project nor Object Type Were Valid'}
                raise serializers.ValidationError(error)

            e = 0 # Check if files uploaded or Not
            u = 0 # Uploaded Count
            count = 1 # Frame generation count
            for video_file in video_files.values():
                saveto = None
                try:
                    # Trying the guess the file type (to verify video)
                    kind = filetype.guess(video_file)
                    filename = None

                    if kind is None:
                        print('Cannot guess file type of video (assuming mp4 just cause, 50% video are kind less with this package)!')
                        filename = '{}.{}'.format(uuid.uuid4().hex, 'mp4')
                    else:
                        print('File extension: %s' % kind.extension)
                        if(kind.extension in ['mp4','mkv','flv','m4v','webm','mov','avi','wmv','mpg']):
                            # Save the video to temp folder
                            filename = '{}.{}'.format(uuid.uuid4().hex, kind.extension)
                        else:
                            print('Not Valid file video extension as filetype check in array of extension.')
                            e = e + 1
                            continue

                    if filename:
                        saveto = os.path.join('media/temp/', filename)
                        saveto = None
                        if not os.path.exists(os.path.join('media/temp/')):
                            saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                        else:
                            saveto = os.path.join('media/temp/', filename)
                            
                        fout = open(saveto, 'wb+')
                        # Iterate through the chunks and write to the file
                        for chunk in video_file.chunks():
                            fout.write(chunk)
                        fout.close()
                        print(filename)
                        # To Capture the frames use cv2
                        vidcap = cv2.VideoCapture(saveto)
                        sec = 0
                        frameRate = 2 # it will capture image in each 2 second
                        success = self.getFrame(vidcap,count,sec,image,project,force_object_type) # Get frame self function made above
                        while success:
                            if count >= 10: ###### Max 10 images from one video ######
                                break
                            count = count + 1
                            sec = sec + frameRate
                            sec = round(sec, 2)
                            success = self.getFrame(vidcap,count,sec,image,project,force_object_type) # Get frame self function made above

                        u = u + 1
                        # Destroy/Close Video and remove from temp
                        cv2.destroyAllWindows()
                        vidcap.release()
                        os.remove(saveto)
                    else:
                        e = e + 1
                except Exception as err:
                    print(err)
                    print('File Failed to Upload - Something went wrong while processing image.')
                    e = e + 1
            
            if(u >= 1 or count > 1): # At least one uploaded good to go
                ###############################
                ##### IF FINE TO CONTINUE #####
                ###############################
                return image
            else: # No Files Upload Throw error
                image.delete()
                error = {'message': str(e)+' Files failed to Upload. (Probably, Files are not type Video or something much worse)'}
                raise serializers.ValidationError(error)
        else:
            error = {'message': 'No Video provided or too much (>7) video provided.'}
            raise serializers.ValidationError(error)

class TestSerializer(serializers.Serializer):
   ping = serializers.CharField(required=False)

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email','full_name','user_type','image')
        read_only = ('id', 'email', 'full_name', 'user_type','image')

class ProjectSerializer(serializers.ModelSerializer):
    unique_name = serializers.SerializerMethodField()

    def get_unique_name(self, obj):
        return obj.unique_name()

    class Meta:
        model = Projects
        fields = ('id','project_name','image','project_desc','unique_name','detect_model','ibm_api_key','offline_model','guest','public','created_at','updated_at')
        read_only_fields = ('id','unique_name','detect_model','created_at', 'updated_at')

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if(validated_data.get('image')):
            instance.image.delete()
        return super().update(instance, validated_data)

class ObjectTypeSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(many=False, read_only=True)
    project_id = serializers.CharField(write_only=True)
    created_by = UserMinimalSerializer(many=False, read_only=True)
    total_classifiers = serializers.SerializerMethodField(read_only=True)

    def get_total_classifiers(self, obj):
        return obj.classifiers.count()

    class Meta:
        model = ObjectType
        fields = ('id','name','project_id','image','instruction','verified','wishlist','total_classifiers','created_by','project','created_at','updated_at')
        read_only_fields = ('id','created_by','created_at', 'updated_at','project')

    def create(self, validated_data):
        request = self.context.get("request")
        if validated_data.get('project_id'): # Validate if "name" is unique
            not_unique = ObjectType.objects.filter(project=validated_data.get('project_id')).filter(name=validated_data.get('name').lower()).all()
            if not_unique:
                error = {'message': 'Object Name needs to be Unique for each Project.'}
                raise serializers.ValidationError(error)

        object_type = ObjectType.objects.create(name=validated_data.get('name').lower(),
                                    created_by=request.user if request else None,
                                    project=Projects.objects.get(id=validated_data.get('project_id')),
                                    image=validated_data.get('image'),
                                    instruction=validated_data.get('instruction'),
                                    verified=True if validated_data.get('verified') else False,
                                    wishlist=True if validated_data.get('wishlist') else False,)
        return object_type

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if validated_data.get('project_id', instance.project_id) and validated_data.get('name', False): # Validate if "name" is unique
            not_unique = ObjectType.objects.filter(project=validated_data.get('project_id', instance.project_id)).filter(name=validated_data.get('name').lower()).all()
            if not_unique and validated_data.get('name').lower() != instance.name:
                error = {'message': 'Object Name needs to be Unique for each Project.'}
                raise serializers.ValidationError(error)

        if(validated_data.get('image')):
            if(instance.image != 'object_types/default.jpg'):
                instance.image.delete()
            instance.image=validated_data.get('image')
        instance.name=validated_data.get('name', instance.name).lower()
        instance.created_by=request.user if request else None
        instance.project=Projects.objects.get(id=validated_data.get('project_id', instance.project_id))
        instance.instruction=validated_data.get('instruction', instance.instruction)
        instance.verified=True if validated_data.get('verified') else False
        instance.wishlist=True if validated_data.get('wishlist') else False
        instance.save()
        return instance
        
class FileUploadSerializer(serializers.ModelSerializer):
    filepath = serializers.SerializerMethodField()
    created_by = UserMinimalSerializer(many=False, read_only=True)

    def get_filepath(self, obj):
        return obj.filepath()

    class Meta:
        model = FileUpload
        fields = ('id','name','file','filepath','created_by','created_at','updated_at')
        read_only_fields = ('id','filepath','created_by','created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get("request")
        fileUpload = FileUpload.objects.create(name=validated_data.get('name'),
                                    created_by=request.user if request else None,
                                    file=validated_data.get('file'))
        return fileUpload

    def update(self, instance, validated_data):
        if(validated_data.get('file')):
            instance.file.delete()
        return super().update(instance, validated_data)

class ObjectTypeMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectType
        fields = ('id','name','image')
        read_only_fields = ('id','name','image')

class OfflineModelMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfflineModel
        fields = ('id','name','model_type','model_format','preprocess','postprocess')
        read_only_fields = ('id','name','model_type','model_format','preprocess','postprocess')

class ClassifierSerializer(serializers.ModelSerializer):
    created_by = UserMinimalSerializer(many=False, read_only=True)
    project = ProjectMinimalSerializer(many=False, read_only=True)
    object_type = ObjectTypeMinimalSerializer(many=False, read_only=True)
    offline_model = OfflineModelMinimalSerializer(many=False, read_only=True)

    project_id = serializers.CharField(write_only=True)
    object_type_id = serializers.CharField(write_only=True)
    offline_model_id = serializers.CharField(write_only=True, allow_blank=True)
    class Meta:
        model = Classifier
        # Other Fields for Validation:
        # source = "offline", "ibm"
        # trained = "true", "false" # i.e. true for pre-trained ibm watson
        # offline_model = id of offline model if offline source selected
        # zip = zipped images (At least 2 zip files with minimum of 10 images each - Make sure the zip file name is exactly what you what the model to be called (go, nogo etc.))
        # negative = zipped negative images (1 Zip file containing negative data - not required)
        # process = process zipped images
        # rotate = rotate zipped images
        # warp = warp images
        # inverse = inverse images
        # is_object_detection = "true" # If Watson Classifier is Object Detection type
        # ibm_api_key = "watson service api key"
        fields = ('id','name','given_name','classes','order','project','project_id','object_type','object_type_id','offline_model','offline_model_id','is_object_detection','ibm_api_key','created_by','created_at','updated_at')
        read_only_fields = ('id','given_name','is_object_detection','created_by','created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get("request")
        # print(request.FILES.getlist('zip'))
        if request.user.is_project_admin and (request.POST.get('source') != "offline" or request.POST.get('trained') != "true"):
            error = {'message': 'Invalid Classifier Attempted to Create. Project Admin must add already created or Offline Models. You cannot create Watson Online Classifier.'}
            raise serializers.ValidationError(error)

        if request.POST.get('source', False) == "offline" and request.POST.get('name') and request.POST.get('offline_model_id',False):
            created = {'data':{'classifier_id':request.POST.get('name'),'name':request.POST.get('name'),'offline_model':request.POST.get('offline_model_id'),'classes':[]}}
        elif request.POST.get('source', False) == "ibm" and request.POST.get('name') and request.POST.get('trained') == "true":
            created = {'data':{'classifier_id':request.POST.get('name'),'name':request.POST.get('name'),'classes':[]}}
        else:
            created = create_classifier(request.FILES.getlist('zip'), request.FILES.get('negative', False), request.POST.get('name'), request.POST.get('object_type_id'), request.POST.get('process', False), request.POST.get('rotate', False), request.POST.get('warp', False), request.POST.get('inverse', False), ibm_api_key=request.POST.get('ibm_api_key',False), project=request.POST.get('project_id',False))
        
        classifier = None
        bad_zip = 0
        if created:
            bad_zip = created.get('bad_zip', 0)
            name = created.get('data', {}).get('classifier_id','')
            given_name = created.get('data', {}).get('name',request.POST.get('name'))
            classes = str(created.get('data', {}).get('classes',[]))
            object_type = None
            project = None
            try:
                project = Projects.objects.get(id=request.POST.get('project_id'))
            except(Projects.DoesNotExist):
                error = {'message': 'Invalid Project Type Selected'}
                raise serializers.ValidationError(error)

            try:
                object_type = ObjectType.objects.filter(project_id=project.id).get(id=request.POST.get('object_type_id'))
            except(ObjectType.DoesNotExist):
                error = {'message': 'Invalid Object Type Selected'}
                raise serializers.ValidationError(error)
            
            if name and given_name and classes and object_type:
                classifier = Classifier()
                classifier.name = name
                classifier.given_name = given_name
                classifier.classes = classes
                classifier.object_type = object_type
                classifier.project = project
                classifier.created_by = request.user
                classifier.order = request.POST.get('order',0)
                if request.POST.get('is_object_detection',False) and request.POST.get('source', "") == "ibm" and request.POST.get('trained') == "true":
                    classifier.is_object_detection = True
                if request.POST.get('ibm_api_key',False) and request.POST.get('source', "") == "ibm":
                    classifier.ibm_api_key = request.POST.get('ibm_api_key')
                if request.POST.get('offline_model_id',False):
                    offline_model = OfflineModel.objects.filter(id=request.POST.get('offline_model')).get()
                    classifier.offline_model = offline_model
                    classifier.classes = json.loads(offline_model.offline_model_labels)
                classifier.save()
                # And unverify the object type
                object_type.verified = False
                object_type.save()
            
            created = json.dumps(created, indent=4)
        else:
            error = {'message': 'Could Not Create Classifier (e.g. Verify zip files are valid and try again)'}
            raise serializers.ValidationError(error)
        
        return classifier

    def update(self, instance, validated_data):
        try:
            request = self.context.get("request")
            instance.name = request.POST.get('name', instance.name)
            if request.POST.get('object_type_id', False):
                object_type = ObjectType.objects.get(id=request.POST.get('object_type_id'))
                instance.object_type = object_type
                # And unverify the object type
                object_type.verified = False
                object_type.save()
            if request.POST.get('project_id', False):
                instance.project = Projects.objects.get(id=request.POST.get('project_id'))
            if request.POST.get('offline_model_id', False):
                offline_model = OfflineModel.objects.get(id=request.POST.get('offline_model_id'))
                instance.offline_model = offline_model
                instance.classes = json.loads(offline_model.offline_model_labels)
            elif request.POST.get('ibm_api_key', False):
                instance.ibm_api_key = request.POST.get('ibm_api_key')
            instance.order = request.POST.get('order', instance.order)
            instance.save()
            return instance
        except:
            error = {'message': 'Unexpected Error Occurred. Possible Invalid Request.'}
            raise serializers.ValidationError(error)

class OfflineModelSerializer(serializers.ModelSerializer):
    created_by = UserMinimalSerializer(many=False, read_only=True)
    filename = serializers.SerializerMethodField()

    def get_filename(self, obj):
        return obj.filename()

    class Meta:
        model = OfflineModel
        # name = Given name
        # model_type = ('CLASSIFIER','Processor'),('OBJECT_DETECT','Object Detect'),('CLASSIFIER','Classifier')
        # model_format = 'py','h5','hdf5','keras'
        # file = Offline Model File
        # offline_model_labels = ["go","nogo"] - NOT REQUIRED FOR Processor (but should have pre or post process true)
        # preprocess = "true" # Is preprocessor
        # postprocess = "true" # Is postprocessor
        fields = ('id','name','model_type','model_format','file','filename','offline_model_labels','preprocess','postprocess','created_by','created_at','updated_at')
        read_only_fields = ('id','filename','created_by','created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get("request")
        offline_model_labels = '[]'
        if type(validated_data.get('offline_model_labels','[]')) == str:
            offline_model_labels = validated_data.get('offline_model_labels','[]')
        else:
            offline_model_labels = json.dumps(validated_data.get('offline_model_labels',[]))

        offline_model = OfflineModel.objects.create(
                            name=validated_data.get('name'),
                            model_type=validated_data.get('model_type'),
                            model_format=validated_data.get('model_format').lower(),
                            file=validated_data.get('file'),
                            offline_model_labels=offline_model_labels,
                            preprocess=validated_data.get('preprocess'),
                            postprocess=validated_data.get('postprocess'),
                            created_by=request.user if request else None
                        )
        return offline_model

    def update(self, instance, validated_data):
        if(validated_data.get('file')):
            instance.file.delete()
        if(validated_data.get('offline_model_labels')):
            offline_model_labels = '[]'
            if type(validated_data.get('offline_model_labels','[]')) == str:
                offline_model_labels = validated_data.get('offline_model_labels','[]')
            else:
                offline_model_labels = json.dumps(validated_data.get('offline_model_labels',[]))
            validated_data['offline_model_labels'] = offline_model_labels
        return super().update(instance, validated_data)

class ContributionSerializer(serializers.ModelSerializer):
    created_by = UserMinimalSerializer(many=False, read_only=True)
    object_type = ObjectTypeMinimalSerializer(many=False, read_only=True)

    def get_unique_name(self, obj):
        return obj.unique_name()

    class Meta:
        model = Contribution
        fields = ('id','title','description','file','object_type','is_helpful','created_by','created_at','updated_at')
        read_only_fields = ('id','created_by','created_at','object_type', 'updated_at')

    def create(self, validated_data):
        try:
            request = self.context.get("request")
            object_type_id = self.context.get('object_type_id',0) # GET object id from url route parameter Passed from Views function
            object_type = ObjectType.objects.get(id=object_type_id)
            if object_type.wishlist:
                contribution = Contribution.objects.create(
                    title=validated_data.get('title'),
                    description=validated_data.get('description'),
                    file=validated_data.get('file', None),
                    object_type=object_type,
                    created_by=request.user
                )
                return contribution
            else:
                raise serializers.ValidationError({"message":"Object Type is Not Receiving Contributions."})
        except(ObjectType.DoesNotExist):
            raise serializers.ValidationError({"message":"Invalid Object Type. The Object type you trying to access does not exist."})

    def update(self, instance, validated_data):
        try:
            request = self.context.get("request")
            object_type_id = self.context.get('object_type_id',0) # GET object id from url route parameter Passed from Views function
            object_type = ObjectType.objects.get(id=object_type_id)

            instance.title = validated_data.get('title', instance.title)
            instance.description = validated_data.get('description', instance.description)
            if (request.user.is_admin or request.user.is_project_admin):
                instance.is_helpful = True if validated_data.get('is_helpful', False) else False

            if(validated_data.get('file')):
                if instance.file:
                    instance.file.delete()
                instance.file = validated_data.get('file', None)
            instance.save()
            return instance
        except(ObjectType.DoesNotExist):
            raise serializers.ValidationError({"message":"Invalid Object Type. The Object type you trying to access does not exist."})
        except(Contribution.DoesNotExist):
            raise serializers.ValidationError({"message":"Invalid Contribution attempted to Edit. It does not exist."})