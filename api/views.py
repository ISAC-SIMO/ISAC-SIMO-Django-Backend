import glob
import io
import json
import os
import re
import sys
import subprocess
import uuid
from datetime import datetime
from http.client import HTTPResponse
from importlib import reload
from django.core.paginator import Paginator
from django.db.models.query import Prefetch

import filetype
import mistune
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import serializers
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
import requests
import urllib
from requests_toolbelt import user_agent
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache

import isac_simo.classifier_list as classifier_list
from api.forms import OfflineModelForm, FileUploadForm
from api.helpers import classifier_detail, create_classifier, markdownToHtml, object_detail, quick_test_detect_image, quick_test_image, quick_test_offline_image, retrain_image, test_image, quick_test_offline_image_pre_post
from api.models import Classifier, ObjectType, OfflineModel, FileUpload
from api.serializers import (ClassifierSerializer, ContributionSerializer, FileUploadSerializer, ImageSerializer, ObjectTypeSerializer, OfflineModelSerializer, ProjectSerializer, TestSerializer, UserSerializer,
                             VideoFrameSerializer)
from main import authorization
from main.authorization import *
from main.models import User
from projects.models import Projects

from .forms import ImageForm
from .models import Contribution, Image, ImageFile
from honeypot.decorators import check_honeypot


def reload_classifier_list():
    try:
        reload(classifier_list)
    except Exception as e:
        print('--------- [ERROR] FAILED TO RELOAD CLASSIFIER LIST MODULE [ERROR:OOPS] --------')

# View All Images
@login_required(login_url=login_url)
def images(request):
    if(is_admin(request.user)):
        images = Image.objects.order_by('-created_at').all().prefetch_related('image_files')[:100]
    elif(is_government(request.user)):
        # NOTE: SHOW IMAGES UPLOADED BY SELF OR LINKED TO PROJECT WHICH THIS USER IS PART OF
        projects = Projects.objects.filter(users__id=request.user.id)
        images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).order_by('-created_at').prefetch_related('image_files').distinct()[:100]
    else:
        # NOTE: SHOW IMAGES UPLOADED BY SELF OR LINKED TO PROJECT WHICH THIS USER IS PART OF
        projects = Projects.objects.filter(users__id=request.user.id)
        images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).order_by('-created_at').prefetch_related('image_files').distinct()[:100]
    return render(request, 'image.html',{'images':images})

# Add Image via Dashboard
@user_passes_test(is_admin, login_url=login_url)
def addImage(request, id = 0):
    if request.method == "GET":
        form = ImageForm(request=request)
        object_types = request.user.get_object_detect_json(request)
        return render(request,"add_image.html",{'form':form, 'object_types':object_types})
    elif request.method == "POST":
        form = ImageForm(request.POST or None, request.FILES or None, request=request)
        files = request.FILES.getlist('image')
        if(len(files) <= 0):
            messages.error(request, "No Image Provided")
            object_types = request.user.get_object_detect_json(request)
            return render(request,"add_image.html",{'form':form, 'object_types':object_types})

        if form.is_valid():
            # CHECK IF either project or object type provided
            project = None
            object_type = None
            force_object_type = None
            # First check if object_type_id is provided
            if request.POST.get('object_type_id', None):
                object_type = ObjectType.objects.filter(id=request.POST.get('object_type_id')).get()
                if object_type:
                    project = object_type.project
                    force_object_type = object_type.name.lower()
            # Else check project
            elif request.POST.get('project', None):
                project = Projects.objects.filter(id=request.POST.get('project')).get()
            
            if not project and not object_type:
                messages.error(request, "Neither Project nor Object Type Were Valid")
                return redirect("images")

            instance = form.save(commit=False)
            if(request.POST.get('user') is None or request.POST.get('user') == ''):
                instance.user_id = request.user.id
            instance.save()

            offline = False
            detect_model = project.detect_model

            try:
                if project.offline_model and project.offline_model.file:
                    offline = True
                    detect_model = project.offline_model
            except:
                offline = False

            i = 0
            for f in files:
                i = i + 1
                photo = ImageFile(image=instance, file=f)
                photo.save()
                
                ################
                ### RUN TEST ###
                ################
                test_image(photo, request.POST.get('title'), request.POST.get('description'), detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())
                    
                if(i>=8):
                    break

            messages.success(request, str(i)+" Image(s) Uploaded Successfully!")
            return redirect("images.update", id=instance.id)
        else:
            messages.error(request, "Invalid Request")
            object_types = request.user.get_object_detect_json(request)
            return render(request,"add_image.html",{'form':form, 'object_types':object_types}) 

    return redirect("images")

# Test Image for ANYONE Guest or Logged In
@check_honeypot
def testImage(request, id = 0):
    dash = request.user and not request.user.is_anonymous
    if dash:
        dash = "master/base.html"
    else:
        dash = "master/blank.html"
    
    if request.method == "GET":
        checks = User().get_object_detect_json(request)
        data = json.dumps(checks);
        # print(checks);
        return render(request,"test_image.html",{'checks':checks, 'dash':dash, 'data':data})
    elif request.method == "POST":
        # try:
        files = request.FILES.getlist('image')
        # print(files)
        if(not files or len(files) <= 0):
            return JsonResponse({'message':'No Image Provided'}, status=400)

        project = None
        object_type = None
        force_object_type = None
        # First check if object_type_id is provided
        if request.POST.get('object_type_id', None):
            if request.POST.get('object_type_id').isdigit():
                object_type = ObjectType.objects.filter(id=request.POST.get('object_type_id')).get()
                if object_type:
                    project = object_type.project
                    force_object_type = object_type.name.lower()
            else:
                return JsonResponse({'message':'Invalid Object Type Provided'}, status=400)
        
        if not project and not object_type:
            return JsonResponse({'message':'Invalid Object Type / Project Provided'}, status=400)

        instance = Image(project=project, description='Via Web Application')
        if request.user and not request.user.is_anonymous:
            instance.user_id = request.user.id
        instance.save()

        offline = False
        detect_model = project.detect_model

        try:
            if project.offline_model and project.offline_model.file:
                offline = True
                detect_model = project.offline_model
        except:
            offline = False

        i = 0
        for f in files:
            i = i + 1
            photo = ImageFile(image=instance, file=f)
            photo.save()
            
            ################
            ### RUN TEST ###
            ################
            test_image(photo, request.POST.get('title'), request.POST.get('description'), detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())
                
            if(i>=8):
                break

        # messages.success(request, str(i)+" Image(s) Uploaded Successfully!")
        return render(request,"test_image_result.html",{'image':instance, 'image_files':instance.image_files, 'auth': (request.user and not request.user.is_anonymous)})

    return JsonResponse({'message':'Something Went Wrong'}, status=400)

# Update Image + Append File + PATCH
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def updateImage(request, id=0):
    try:
        image = Image.objects.get(id=id)
        image_files = ImageFile.objects.filter(image_id=image.id)
        verified_list = {}
        can_retrain = False
        min_images_to_zip = 10
        if settings.DEBUG:
            min_images_to_zip = 2
        #NOTE: 10 minimum zipped images is required to re-train a go,nogo,etc.. model (calculated below)

        if request.method == "GET":
            for image_file in image_files:
                if image_file.verified and image_file.result and image_file.object_type and not image_file.retrained:
                    # TO CREATE STRUCTURE OF #
                    # {
                    #     "wall":{
                    #         "go": 10,
                    #         "nogo":5,
                    #     },
                    #     "rebar":{
                    #         "10mm": 10,
                    #         "20mm":5,
                    #     }
                    # }
                    verified_list[image_file.object_type.lower()] = verified_list.get(image_file.object_type.lower(),{})
                    verified_list.get(image_file.object_type.lower(),{})[image_file.result.lower()] = verified_list.get(image_file.object_type.lower(),{}).get(image_file.result.lower(),0) + 1
                    # print(verified_list)
                    if verified_list.get(image_file.object_type.lower(),{}).get(image_file.result.lower(),0) >= min_images_to_zip:
                        can_retrain = True

            form = ImageForm(instance=image, request=request)
            user_name = image.user.full_name if image.user else 'Guest'
            user_id = image.user.id if image.user else 0
            object_types = request.user.get_object_detect_json(request)
            return render(request,"add_image.html",{'form':form, 'user_name':user_name, 'user_id':user_id, 'id':id, 'image_files':image_files, 'verified_list':verified_list, 'can_retrain':can_retrain, 'object_types': object_types})
        elif request.method == "POST":
            files = request.FILES.getlist('image')
            form = ImageForm(request.POST or None, request.FILES or None, instance=image, request=request)
            if form.is_valid():
                # CHECK IF either project or object type provided
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
                
                if not project and not object_type and len(files) > 0:
                    messages.error(request, "Neither Project nor Object Type Were Valid")
                    return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))
                    
                instance = form.save(commit=False)
                instance.save()

                if len(files) > 0:
                    offline = False
                    detect_model = project.detect_model

                    try:
                        if project.offline_model and project.offline_model.file:
                            offline = True
                            detect_model = project.offline_model
                    except:
                        offline = False

                i = 0
                for f in files:
                    i = i + 1
                    photo = ImageFile(image=instance, file=f)
                    photo.save()
                    
                    ################
                    ### RUN TEST ###
                    ################
                    test_image(photo, request.POST.get('title'), request.POST.get('description'), detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())

                    if(i>=8):
                        break

                messages.success(request, "Image Details Edited Successfully!")
                if i > 0:
                    messages.success(request, str(i) + " New Images Tested")
            else:
                messages.error(request, "Invalid Request")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

        return redirect("images.update", id=instance.id)
    except(Image.DoesNotExist):
        messages.error(request, "Invalid Image attempted to Edit")
        return redirect("images")

# Delete Image
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def deleteImage(request, id=0):
    try:
        if request.method == "POST":
            if request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=request.user.id)
                image = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).get(id=id)
            else:
                image = Image.objects.get(id=id)
            for i in image.image_files.all():
                i.file.delete()
                i.delete()
            image.delete()
            messages.success(request, 'Image Data Deleted Successfully!')
            return redirect('images')
        else:
            messages.error(request, 'Failed to Delete!')
            return redirect('images')
    except(Image.DoesNotExist):
        messages.error(request, "Invalid Image attempted to Delete")
        return redirect("images")

# This is users image retrain - not from inside IBM watson sidebar menu
# Retrain Images files uploaded by API after checking verified status and then send zip to ibm
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def retrainImage(request, id):
    try:
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id)
            image = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).get(id=id)
        else:
            image = Image.objects.get(id=id)

        if not image.project:
            messages.error(request, "Unable to Retrain. Images are not linked to any Project. It will only re-train if images are linked to a project so that it can retrain all classifiers for that project.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

        image_files = ImageFile.objects.filter(image_id=image.id)
        verified_list = {}
        image_file_list = {}
        image_file_id_list = {}
        can_retrain = False
        min_images_to_zip = 10
        if settings.DEBUG:
            min_images_to_zip = 2
        #NOTE: 10 minimum zipped images is required to re-train a go,nogo,etc.. model (calculated below)

        if request.method != "POST":
            messages.error(request, "Re-Train Request was improperly sent")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))
        elif request.method == "POST":
            for image_file in image_files:
                if image_file.verified and image_file.result and image_file.file and image_file.object_type:
                    verified_list[image_file.object_type.lower()] = verified_list.get(image_file.object_type.lower(),{})
                    verified_list.get(image_file.object_type.lower(),{})[image_file.result.lower()] = verified_list.get(image_file.object_type.lower(),{}).get(image_file.result.lower(),0) + 1
                    # print(verified_list)

                    image_file_list[image_file.object_type.lower()] = image_file_list.get(image_file.object_type.lower(),{})
                    image_file_list.get(image_file.object_type.lower(),{})[image_file.result.lower()] = image_file_list.get(image_file.object_type.lower(),{}).get(image_file.result.lower(),[]) + [image_file.file.url]
                    # print(image_file_list)
                    
                    image_file_id_list[image_file.object_type.lower()] = image_file_id_list.get(image_file.object_type.lower(),{})
                    image_file_id_list.get(image_file.object_type.lower(),{})[image_file.result.lower()] = image_file_id_list.get(image_file.object_type.lower(),{}).get(image_file.result.lower(),[]) + [image_file.id]
                    # print(image_file_id_list)

                    # verified_list[image_file.result.lower()] = verified_list.get(image_file.result.lower(),0) + 1
                    # image_file_list[image_file.result.lower()] = image_file_list.get(image_file.result.lower(),[]) + [image_file.file.url]
                    # image_file_id_list[image_file.result.lower()] = image_file_id_list.get(image_file.result.lower(),[]) + [image_file.id]
                    # print(image_file_list)
                    print(verified_list)

            for p_key, p_value in verified_list.items():
                # print(p_value)
                for key, value in p_value.items():
                    if value >= min_images_to_zip:
                        can_retrain = True
                        print(image_file_list.get(p_key,{}).get(key,[]))
                        # Image File List(arr), project, object_type, result
                        retrain_response = retrain_image(image_file_list.get(p_key,{}).get(key,[]), image.project.unique_name(), p_key, key, noIndexCheck=True)

                        if retrain_response:
                            messages.success(request, "Zipped and Sent for Re-Training")
                            # Use id list to update in db - the retrained boolean status
                            print(image_file_id_list.get(p_key,{}).get(key,[]))
                            for id in image_file_id_list.get(p_key,{}).get(key,[]):
                                image_file = ImageFile.objects.get(id=id)
                                image_file.retrained = True
                                image_file.save()
                        else:
                            messages.error(request, "Failed to Re-Train")
                            print('Failed to re-train')
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))
    except(Image.DoesNotExist):
        messages.error(request, "This Image Model probably does not exist")
        return redirect("images.add")

# Delete Image Specific File
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def deleteImageFile(request, id):
    try:
        if request.method == "POST":
            if request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=request.user.id)
                images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects))
                image_file = ImageFile.objects.filter(Q(image__in=images)).get(id=id)
            else:
                image_file = ImageFile.objects.get(id=id)
            image_file.file.delete()
            image_file.delete()
            messages.success(request, 'Image Deleted Successfully!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            messages.error(request, 'Invalid Request!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    except(ImageFile.DoesNotExist):
        messages.error(request, "Invalid Image File attempted to Delete")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

# Re-Test Image Specific File
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def retestImageFile(request, id):
    try:
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id)
            images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects))
            image_file = ImageFile.objects.filter(Q(image__in=images)).get(id=id)
        else:
            image_file = ImageFile.objects.get(id=id)

        # CHECK IF either project or object type provided
        project = None
        object_type = None
        force_object_type = None
        # First check if object_type_id is provided
        if request.GET.get('object_type_id', None):
            object_type = ObjectType.objects.filter(id=request.GET.get('object_type_id')).get()
            if object_type:
                project = object_type.project
                force_object_type = object_type.name.lower()
        # Else check project_id
        elif image_file.image.project:
            project = image_file.image.project
        
        if not project and not object_type:
            messages.error(request, "Neither Project nor Object Type Were Valid")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))
        
        offline = False
        detect_model = project.detect_model

        try:
            if project.offline_model and project.offline_model.file:
                offline = True
                detect_model = project.offline_model
        except:
            offline = False
        
        if not image_file.result or not image_file.score:
            test_status = test_image(image_file, detect_model=detect_model, project=project.unique_name(), offline=offline, force_object_type=force_object_type, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())
            if test_status:
                messages.success(request, 'Image Tested Successfully.')
            else:
                messages.error(request, 'Testing Image Failed !!')
        else:
            messages.error(request, 'Image was already tested.')
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    except(ImageFile.DoesNotExist):
        messages.error(request, "Invalid Image File attempted to Re-test")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

# Re-Test Image Specific File
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def verifyImageFile(request, id):
    try:
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id)
            images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects))
            image_file = ImageFile.objects.filter(Q(image__in=images)).get(id=id)
        else:
            image_file = ImageFile.objects.get(id=id)
        image_file.result = request.POST.get('test-result',image_file.result).lower()
        image_file.score = request.POST.get('test-score',image_file.score)
        image_file.object_type = request.POST.get('test-object-type',image_file.object_type).lower()
        if request.POST.get('test-verified',False):
            image_file.verified = True
        else:
            image_file.verified = False
        image_file.save()

        # NOW TODO: SEND Images to SPSS or continues or IBM AI model and retrain it or something like that

        messages.success(request, "Image File Updated - It is now " + ('verified' if image_file.verified else 'un-verified'))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    except(ImageFile.DoesNotExist):
        messages.error(request, "Invalid Image File attempted to Verify")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

# Image Custom Train to IBM
# OR Retrain Image in uploaded by admin into ibm model selected
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonTrain(request):
    if request.method == "GET":
        return render(request, 'train.html',{'classifier_list':classifier_list.value()})
    elif request.method == "POST":
        zipped = 0
        image_file_list = []
        for image in request.FILES.getlist('images'):
            kind = filetype.guess(image)
            if kind is None:
                print('Cannot guess file type!')
            else:
                filename = '{}.{}'.format(uuid.uuid4().hex, kind.extension)
                destination = open(settings.MEDIA_ROOT + '/temp/' + filename, 'wb+')
                for chunk in image.chunks():
                    destination.write(chunk)
                destination.close()
                if not os.path.exists(os.path.join('media/temp/')):
                    image_file_list = image_file_list + [os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename]
                else:
                    image_file_list = image_file_list + [os.path.join('media/temp/', filename)]
                zipped += 1
                # print(image_file_list)

        min_image_required = 10
        if settings.DEBUG:
            min_image_required = 2

        # we have "model" in request. If Model is all or not provided then all images are re-trained in all classifiers of object type given, else only on selected classifier (it is the last parameter in retrain function)
        if zipped >= min_image_required and image_file_list and request.POST.get('project', False) and request.POST.get('object', False) and request.POST.get('result', False):
            retrain_status = retrain_image(image_file_list, request.POST.get('project'), request.POST.get('object').lower(), request.POST.get('result').lower(), 'temp', request.POST.get('model', False), request.POST.get('process', False), request.POST.get('rotate', False), request.POST.get('warp', False), request.POST.get('inverse', False), request=request)
            print(retrain_status)
            if retrain_status:
                messages.success(request,str(zipped) + ' images zipped and was sent to retrain in ' + str(retrain_status) + ' classifier(s). (Retraining takes time)')
                messages.info(request,'Project: '+request.POST.get('project')+', Object: '+request.POST.get('object')+' , Classifier: '+request.POST.get('model')+' , Result: '+request.POST.get('result'))
            else:
                messages.error(request,str(zipped) + ' images zipped but failed to retrain')
        else:
            messages.error(request,str(zipped) + ' valid Image(s). At least 10 required. Or Invalid input.')

        print(str(len(image_file_list)) + ' original images...')
        for image_file in image_file_list:
            os.remove(image_file)
            pass

        reload_classifier_list()
        return redirect('watson.train')
    
    return redirect('dashboard')

@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierList(request):
    classifiers = False
    object_type = False
    if request.user.user_type == 'project_admin':
        projects = Projects.objects.filter(users__id=request.user.id)
        if request.GET.get('object_type', False):
            classifiers = Classifier.objects.order_by('-object_type','order').filter(Q(created_by=request.user) | Q(project__in=projects)).filter(object_type=request.GET.get('object_type')).all()
            object_type = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').get(id=request.GET.get('object_type'))
        else:
            classifiers = Classifier.objects.order_by('-object_type','order').filter(Q(created_by=request.user) | Q(project__in=projects)).all()
            object_type = False
    else:
        if request.GET.get('object_type', False):
            classifiers = Classifier.objects.order_by('-object_type','order').filter(object_type=request.GET.get('object_type')).all()
            object_type = ObjectType.objects.filter(id=request.GET.get('object_type')).get().name
        else:
            classifiers = Classifier.objects.order_by('-object_type','order').all()
            object_type = False
    
    return render(request, 'list_classifier.html',{'classifiers':classifiers,'object_type':object_type})

@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierOrder(request, id): # id = object_type_id
    if request.method == "GET":
        classifiers = False
        object_type = False
        if request.user.user_type == 'project_admin':
            projects = Projects.objects.filter(users__id=request.user.id)
            classifiers = Classifier.objects.order_by('-object_type').filter(Q(created_by=request.user) | Q(project__in=projects)).filter(object_type=id).order_by('order').all()
            object_type = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').get(id=id)
        else:
            classifiers = Classifier.objects.order_by('-object_type').filter(object_type=id).order_by('order').all()
            object_type = ObjectType.objects.filter(id=id).get()
        
        return render(request, 'order_classifier.html',{'classifiers':classifiers,'object_type':object_type})
    elif request.method == "POST":
        classifier_ids = json.loads(request.POST.get('classifiers','[]'))
        projects = Projects.objects.filter(users__id=request.user.id)
        error = 0
        for idx, classifier_id in enumerate(classifier_ids):
            try:
                if request.user.user_type == 'project_admin':
                    classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).filter(object_type=id).get(id=classifier_id)
                else:
                    classifier = Classifier.objects.filter(object_type=id).get(id=classifier_id)
                classifier.order = idx + 1
                classifier.save()
                # THEN reset verified to False
                object_type = ObjectType.objects.filter(id=id).get()
                object_type.verified = False
                object_type.save()
            except(Classifier.DoesNotExist):
                error = error + 1

        messages.success(request, 'Classifiers Order Updated')
        if error > 0:
            messages.error(request, 'But, '+error+' did not succeed.')
        reload_classifier_list()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    else:
        messages.error(request, 'Invalid Request for Ordering Classifiers')
        return redirect('dashboard')

# Classifier Details of IBM
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifier(request):
    authorized_classifier_list = {}
    projects = []
    if request.user.user_type == 'project_admin':
        projects = Projects.objects.filter(users__id=request.user.id).order_by('created_at').all().prefetch_related(Prefetch('object_types', queryset=ObjectType.objects.order_by('created_at').all().prefetch_related(Prefetch('classifiers', queryset=Classifier.objects.order_by('-object_type','order')))))
    else:
        projects = Projects.objects.order_by('created_at').all().prefetch_related(Prefetch('object_types', queryset=ObjectType.objects.order_by('created_at').all().prefetch_related(Prefetch('classifiers', queryset=Classifier.objects.order_by('-object_type','order')))))

    for project in projects:
        if not authorized_classifier_list.get(project.unique_name(), False):
            authorized_classifier_list[project.unique_name()] = {}

        if project.object_types.all().count():
            for object_type in project.object_types.all():
                if object_type.name.lower() not in authorized_classifier_list.get(project.unique_name(),[]):
                    authorized_classifier_list[project.unique_name()][object_type.name.lower()] = []
                
                if object_type.classifiers.all().count():
                    for classifier in object_type.classifiers.all():
                        if classifier.name not in authorized_classifier_list.get(project.unique_name(),[]).get(object_type.name.lower(),[]):
                            authorized_classifier_list[project.unique_name()][object_type.name.lower()] = authorized_classifier_list[project.unique_name()][object_type.name.lower()] + [classifier.name]

    if request.method != "POST":
        return render(request, 'classifiers.html',{'classifier_list':authorized_classifier_list})
    elif request.method == "POST":
        detail = classifier_detail(request.POST.get('project', False), request.POST.get('object', False), request.POST.get('model', False))
        if detail:
            detail = json.dumps(detail, indent=4)
        else:
            detail = 'Could Not Fetch Classifier Detail'
        
        reload_classifier_list()
        return render(request, 'classifiers.html',{'classifier_list':authorized_classifier_list, 'detail':detail, 'project':request.POST.get('project', False), 'object':request.POST.get('object', False), 'model':request.POST.get('model', False)})

# Create Custom Classifiers with zip data
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierCreate(request):
    if request.method == "GET":
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
            object_types = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').all()
            
            offlineModels = OfflineModel.objects.filter(created_by=request.user).filter(model_type='CLASSIFIER').all()
            return render(request, 'create_classifier.html', {'object_types':object_types, 'projects':projects, 'offlineModels':offlineModels})
        else:
            object_types = ObjectType.objects.order_by('-created_at').all()
            projects = Projects.objects.order_by('project_name').all()
            offlineModels = OfflineModel.objects.filter(model_type='CLASSIFIER').all()
            return render(request, 'create_classifier.html', {'object_types':object_types, 'projects':projects, 'offlineModels':offlineModels})
    elif request.method == "POST":
        print(request.FILES.getlist('zip'))
        # NOTE: FOR PROJECT USER. They can only add offline or already added watson models (cannot create themselves manually)
        # if request.user.is_project_admin and (request.POST.get('source') != "offline" or request.POST.get('trained') != "true"):
        #     created = 'Invalid Classifier Attempted to Create. Project Admin must add already created or Offline Models. You cannot create Watson Online Classifier. (Contact Admin Please)'
        #     return render(request, 'create_classifier.html',{'created':created, 'bad_zip':0})

        if request.POST.get('source', False) == "offline" and request.POST.get('name') and request.POST.get('offlineModel',False):
            created = {'data':{'classifier_id':request.POST.get('name'),'name':request.POST.get('name'),'offline_model':request.POST.get('offlineModel'),'classes':[]}}
        elif request.POST.get('source', False) == "ibm" and request.POST.get('name') and request.POST.get('trained') == "true":
            created = {'data':{'classifier_id':request.POST.get('name'),'name':request.POST.get('name'),'classes':[]}}
        else:
            created = create_classifier(request.FILES.getlist('zip'), request.FILES.get('negative', False), request.POST.get('name'), request.POST.get('object_type'), request.POST.get('process', False), request.POST.get('rotate', False), request.POST.get('warp', False), request.POST.get('inverse', False), ibm_api_key=request.POST.get('ibm_api_key',False), project=request.POST.get('project',False), ibm_service_url=request.POST.get('ibm_service_url',''))
        
        bad_zip = 0
        if created:
            bad_zip = created.get('bad_zip', 0)
            name = created.get('data', {}).get('classifier_id','')
            given_name = created.get('data', {}).get('name',request.POST.get('name'))
            classes = str(created.get('data', {}).get('classes',[]))
            object_type = None
            project = None
            try:
                object_type = ObjectType.objects.get(id=request.POST.get('object_type'))
            except(ObjectType.DoesNotExist):
                messages.error(request, 'Object Was Invalid')

            try:
                project = Projects.objects.get(id=request.POST.get('project'))
            except(Projects.DoesNotExist):
                messages.error(request, 'Project Was Invalid')
            
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
                if request.POST.get('ibm_service_url',False) and request.POST.get('source', "") == "ibm":
                    classifier.ibm_service_url = request.POST.get('ibm_service_url')
                if request.POST.get('offlineModel',False):
                    offline_model = OfflineModel.objects.filter(id=request.POST.get('offlineModel')).get()
                    classifier.offline_model = offline_model
                    classifier.classes = json.loads(offline_model.offline_model_labels)
                classifier.save()
                # And unverify the object type
                object_type.verified = False
                object_type.save()
            
            created = json.dumps(created, indent=4)
        else:
            created = 'Could Not Create Classifier (Verify zip files are valid and try again)'
        
        reload_classifier_list()
        return render(request, 'create_classifier.html',{'created':created, 'bad_zip':bad_zip})

    messages.error(request, 'Invalid Request')
    return redirect('dashboard')

# Watson Classifier Edit
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierEdit(request, id):
    if(request.method == "POST" and request.POST.get('object_type', False) 
        and request.POST.get('project', False)
        and request.POST.get('order', False)
    ):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
                classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=id)
            else:
                classifier = Classifier.objects.get(id=id)
            classifier.name = request.POST.get('name')
            object_type = ObjectType.objects.get(id=request.POST.get('object_type'))
            classifier.object_type = object_type
            classifier.project = Projects.objects.get(id=request.POST.get('project'))
            if request.POST.get('offlineModel', False):
                offline_model = OfflineModel.objects.get(id=request.POST.get('offlineModel'))
                classifier.offline_model = offline_model
                classifier.classes = json.loads(offline_model.offline_model_labels)
                classifier.ibm_api_key = ''
            else:
                classifier.is_object_detection = True if request.POST.get('is_object_detection', False) else False
                classifier.ibm_api_key = request.POST.get('ibm_api_key','')
                classifier.ibm_service_url = request.POST.get('ibm_service_url','')
            classifier.order = request.POST.get('order', 0)
            classifier.save()
            # And unverify the object type
            object_type.verified = False
            object_type.save()
            messages.success(request, 'Classifier Updated (Order set to: '+ str(request.POST.get('order', 0)) +')')
            reload_classifier_list()
            return redirect('watson.classifier.list')
        except(Classifier.DoesNotExist):
            messages.error(request, 'Classifier Not Found')
            return redirect('watson.classifier.list')
    elif(request.method == "GET"):
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
            classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=id)
            object_types = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').all()
            offlineModels = OfflineModel.objects.filter(Q(created_by=request.user) | Q(id=classifier.offline_model_id)).filter(model_type='CLASSIFIER').distinct().all()
            return render(request, 'edit_classifier.html', {'classifier':classifier, 'object_types':object_types, 'projects':projects, 'offlineModels':offlineModels})
        else:
            classifier = Classifier.objects.get(id=id)
            object_types = ObjectType.objects.order_by('-created_at').all()
            projects = Projects.objects.order_by('project_name').all()
            offlineModels = OfflineModel.objects.filter(model_type='CLASSIFIER').all()
            return render(request, 'edit_classifier.html', {'classifier':classifier, 'object_types':object_types, 'projects':projects, 'offlineModels':offlineModels})
    else:
        messages.error(request, 'Classifier Not Edited Bad Request')
        return redirect('watson.classifier.list')

# Watson Classifier Delete
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierDelete(request, id):
    if(request.method == "POST"):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
                classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=id)
            else:
                classifier = Classifier.objects.get(id=id)
            
            # And unverify the object type
            object_type = classifier.object_type
            object_type.verified = False
            object_type.save()
            
            classifier.delete()
            messages.success(request, 'Classifier Deleted (Images will not be passed through this again)')
            reload_classifier_list()
            return redirect('watson.classifier.list')
        except(Classifier.DoesNotExist):
            messages.success(request, 'Classifier Not Found')
            return redirect('watson.classifier.list')
    else:
        messages.success(request, 'Classifier Not Deleted')
        return redirect('watson.classifier.list')

# Watson Classifier Test - Simple image test
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonClassifierTest(request, id):
    if(request.method == "POST"):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
                classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=id)
            else:
                classifier = Classifier.objects.get(id=id)

            # IF THIS CLASSIFIER HAS OFFLINE MODEL THEN
            if classifier.offline_model:
                # IF IS A PRE / POST TEST
                if classifier.offline_model.preprocess or classifier.offline_model.postprocess:
                    quick_test_image_result = quick_test_offline_image_pre_post(request.FILES.get('file', False), classifier, request, fake_score=request.POST.get('fake_score', 0), fake_result=request.POST.get('fake_result', ""))
                    if quick_test_image_result:
                        if classifier.offline_model.preprocess:
                            request.session['image'] = quick_test_image_result.get('image',False)
                        else:
                            request.session['test_result'] = json.dumps(quick_test_image_result.get('data','No Test Data'), indent=4)
                    else:
                        messages.error(request, 'Unable to Test. Pre-Process / Post-Process failed or did not return a result.')
                    
                    return redirect('watson.classifier.test', id=id)
                    
                quick_test_image_result = quick_test_offline_image(request.FILES.get('file', False), classifier)
            # IF ONLINE MODEL which is_object_detection
            elif classifier.is_object_detection:
                if os.environ.get('PROJECT_FOLDER',False):
                    project_folder = os.environ.get('PROJECT_FOLDER','') + '/'
                else:
                    project_folder = ''
                quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), classifier.name, offline=False, project_folder=project_folder, ibm_api_key=classifier.ibm_api_key, ibm_service_url=classifier.get_ibm_service_url())
                if quick_test_image_result:
                    if isinstance(quick_test_image_result, dict) and quick_test_image_result.get("error", False):
                        request.session['test_result'] = json.dumps(quick_test_image_result, indent=4)
                        messages.error(request, 'Nothing was Detected.')
                    elif len(quick_test_image_result) > 0:
                        request.session['test_result'] = json.dumps(quick_test_image_result, indent=4)
                        messages.success(request, 'Classifier (Object Detect Model) Test Success.')
                        messages.success(request, 'Score: '+str(quick_test_image_result[0]['pipeline']['score'])+' | Class: '+str(quick_test_image_result[0]['pipeline']['result']))
                    else:
                        request.session['test_result'] = quick_test_image_result
                        messages.error(request, 'Test Success, but Bad Response type')
                    return redirect('watson.classifier.test', id=id)
            # ELSE ONLINE MODEL THEN
            else:
                quick_test_image_result = quick_test_image(request.FILES.get('file', False), classifier.name, classifier)
            
            if quick_test_image_result:
                request.session['test_result'] = json.dumps(quick_test_image_result.get('data','No Test Data'), indent=4)
                messages.success(request, 'Classifier Test Success.')
                messages.success(request, 'Score: '+str(quick_test_image_result.get('score','0'))+' | Class: '+str(quick_test_image_result.get('result','Not Found')))
            else:
                messages.error(request, 'Unable to Test (Make sure Classifier is valid and is in ready state)')

            return redirect('watson.classifier.test', id=id)
        except(Classifier.DoesNotExist):
            messages.error(request, 'Classifier Not Found')
            return redirect('watson.classifier.list')
        except Exception as e:
            print(e)
            messages.error(request, 'Classifier Test Failed')
            return redirect('watson.classifier.test', id=id)

    elif(request.method == "GET"):
        if request.user.user_type == 'project_admin':
            projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
            classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=id)
        else:
            classifier = Classifier.objects.get(id=id)
        test_result = request.session.pop('test_result', False)
        image = request.session.pop('image', False)
        return render(request, 'test_classifier.html', {'classifier':classifier, 'test_result':test_result, 'image':image})
    else:
        messages.success(request, 'Bad Request for CLassifier Test')
        return redirect('watson.classifier.test')

# Watson object detail fetch from ibm
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObject(request):
    if request.method != "POST":
        default_object_model = classifier_list.detect_object_model_id
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').values('id','detect_model','project_name','offline_model').distinct()
        else:
            projects = Projects.objects.all().values('id','detect_model','project_name','offline_model').distinct()
        return render(request, 'objects_detail.html',{'default_object_model':default_object_model,'projects':projects})
    elif request.method == "POST":
        detail = None
        object_id = request.POST.get('object_id', False)
        project = Projects.objects.get(id=object_id)
        
        # IF Watson Object Detail is a offline Model type
        if project.offline_model:
            offline_model = project.offline_model
            if offline_model:
                try:
                    offlineModelLabels = json.loads(offline_model.offline_model_labels)
                except Exception as e:
                    offlineModelLabels = []
                detail = json.dumps({
                    'offline': True,
                    'name': offline_model.name,
                    'type': offline_model.model_type,
                    'format': offline_model.model_format,
                    'labels': offlineModelLabels,
                    'url': offline_model.file.url
                }, indent=4)
                return render(request, 'objects.html',{'detail':detail,'object_id':offline_model.name})
        
        # If not offline model try online
        try:
            detail = object_detail(project.detect_model, project.ibm_api_key, project.get_ibm_service_url())
            if detail:
                detail = json.dumps(detail, indent=4)
            else:
                detail = 'Could Not Fetch List Object Detail Metadata'
        except Exception as e:
            print(e)
            detail = 'Could Not Fetch List Object Detail Metadata (Server Error or Object Not Found)'
        finally:
            return render(request, 'objects.html',{'detail':detail,'object_id':object_id})

# Watson Object Type List
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObjectList(request):
    if request.user.user_type == 'project_admin':
        if request.GET.get('project', False):
            project = Projects.objects.filter(users__id=request.user.id).get(id=request.GET.get('project'))
            object_types = ObjectType.objects.order_by('-created_at').filter(project=request.GET.get('project')).all()
            project_filter = project.project_name
        else:
            projects = Projects.objects.filter(users__id=request.user.id)
            object_types = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').order_by('project').all()
            project_filter = False
    else:
        if request.GET.get('project', False):
            object_types = ObjectType.objects.order_by('-created_at').filter(project=request.GET.get('project')).all()
            project_filter = Projects.objects.filter(id=request.GET.get('project')).get().project_name
        else:
            object_types = ObjectType.objects.order_by('-created_at').order_by('project').all()
            project_filter = False

    if request.user.user_type == 'project_admin':
        projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
    else:
        projects = Projects.objects.order_by('project_name').all()

    return render(request, 'create_objects.html', {'object_types':object_types, 'projects':projects, 'project_filter':project_filter})

# Watson Object Type Create local
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObjectCreate(request):
    if(request.method == "POST" and request.POST.get('object_type', False)):
        countries = request.POST.getlist("countries") or []
        if countries and len(countries) > 0:
            countries = ",".join(countries)
        else:
            countries = ""

        check_unique = None
        try:
            if request.user.is_project_admin:
                project = Projects.objects.filter(users__id=request.user.id).get(id=request.POST.get('project'))
        except(Projects.DoesNotExist):
            messages.error(request, 'Invalid Project Selected')
            return redirect('watson.object.list')

        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # Edit
            object_type = ObjectType.objects.filter(id=request.POST.get('id')).get()
            if request.POST.get('project') and request.POST.get('project') != "0":
                check_unique = ObjectType.objects.filter(project=request.POST.get('project')).filter(name=request.POST.get('object_type').lower()).all()
            if not check_unique or request.POST.get('object_type').lower() == object_type.name:
                object_type.name = request.POST.get('object_type').lower()
                if request.POST.get('project') and request.POST.get('project') != "0":
                    object_type.project = Projects.objects.filter(id=request.POST.get('project')).get()
                object_type.instruction = request.POST.get('instruction')
                object_type.verified = False
                if request.FILES.get('image'):
                    if(object_type.image != 'object_types/default.jpg'):
                        object_type.image.delete()
                    object_type.image = request.FILES.get('image')
                object_type.countries = countries
                object_type.save()
                messages.success(request, 'Check / Object Type Updated')
                reload_classifier_list()
                return redirect('watson.object.list')
            else:
                messages.error(request, 'Check Edit Failed - That Object Name already exists for this Project')
                return redirect('watson.object.list')
        else:
            # Create
            if request.POST.get('project') and request.POST.get('project') != "0":
                check_unique = ObjectType.objects.filter(project=request.POST.get('project')).filter(name=request.POST.get('object_type').lower()).all()
            if not check_unique:
                object_type = ObjectType()
                object_type.name = request.POST.get('object_type').lower()
                if request.POST.get('project') and request.POST.get('project') != "0":
                    object_type.project = Projects.objects.filter(id=request.POST.get('project')).get()
                object_type.created_by = request.user
                object_type.instruction = request.POST.get('instruction')
                if request.FILES.get('image'):
                    object_type.image = request.FILES.get('image')
                object_type.countries = countries
                object_type.save()
                messages.success(request, 'Check / Object Type Added')
                reload_classifier_list()
                return redirect('watson.object.list')
            else:
                messages.error(request, 'Check Not Added - Object Name already exists for this Project')
                return redirect('watson.object.list')
    else:
        messages.error(request, 'Check Not Added')
        return redirect('watson.object.list')

# Watson Object Type Delete
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObjectDelete(request, id):
    if(request.method == "POST"):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id)
                object_type = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').get(id=id)
            else:
                object_type = ObjectType.objects.get(id=id)
            if(object_type.image != 'object_types/default.jpg'):
                object_type.image.delete()
            object_type.delete()
            messages.success(request, 'Check / Object Type Deleted (Related Models are now left without any checks)')
            reload_classifier_list()
            return redirect('watson.object.list')
        except(ObjectType.DoesNotExist):
            messages.success(request, 'Check Not Found')
            return redirect('watson.object.list')
    else:
        messages.error(request, 'Check Not Deleted')
        return redirect('watson.object.list')

# Watson Object Type Verify or Un-Verify
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObjectVerify(request, id):
    if(request.method == "POST"):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id)
                object_type = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').get(id=id)
            else:
                object_type = ObjectType.objects.get(id=id)
            object_type.verified = not object_type.verified
            object_type.save()
            messages.success(request, 'Check / Object Type '+ ("Verified" if object_type.verified else "Un-Verified"))
            return redirect('watson.object.list')
        except(ObjectType.DoesNotExist):
            messages.success(request, 'Object Not Found')
            return redirect('watson.object.list')
    else:
        messages.error(request, 'Invalid Request')
        return redirect('watson.object.list')

# Watson Object Type Add/Remove from Wishlist
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def watsonObjectWishlist(request, id):
    if(request.method == "POST"):
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id)
                object_type = ObjectType.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).order_by('-created_at').get(id=id)
            else:
                object_type = ObjectType.objects.get(id=id)
            object_type.wishlist = not object_type.wishlist
            object_type.save()
            messages.success(request, 'Check / Object Type has been '+ ("Added to Wishlist (Contribution are now accepted if the Project is marked Public)" if object_type.wishlist else "Removed from Wishlist (Contribution has been paused.)"))
            return redirect('watson.object.list')
        except(ObjectType.DoesNotExist):
            messages.success(request, 'Object Not Found')
            return redirect('watson.object.list')
    else:
        messages.error(request, 'Invalid Request')
        return redirect('watson.object.list')

##################
# OFFLINE MODELS #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModel(request):
    if request.user.user_type == 'project_admin':
        models = OfflineModel.objects.filter(created_by=request.user).order_by('name')
    else:
        models = OfflineModel.objects.all().order_by('name')
    return render(request, 'offline_model/list.html',{'models':models})

#########################
# OFFLINE MODELS CREATE #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelCreate(request):
    if request.method == "GET":
        form = OfflineModelForm()
        offlineModelLabels = []
        return render(request,"offline_model/create.html",{'form':form,'offlineModelLabels':offlineModelLabels})
    elif request.method == "POST":
        form = OfflineModelForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.created_by = User.objects.get(id=request.user.id)
            instance.offline_model_labels = json.dumps(request.POST.getlist('offline_model_labels'))
            instance.save()
            reload_classifier_list()
            messages.success(request, "New Offline Model Added")
        else:
            messages.error(request, "Invalid Request")
            return render(request,"offline_model/create.html",{'form':form})  

    return redirect("offline.model.list")

#######################
# OFFLINE MODELS EDIT #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelEdit(request, id):
    try:
        if request.user.user_type == 'project_admin':
            offlineModel = OfflineModel.objects.filter(id=id).filter(created_by=request.user).get()
        else:
            offlineModel = OfflineModel.objects.filter(id=id).get()
        offlineModelFile = os.path.join(offlineModel.file.url.replace('/media/','media/'))

        if request.method == "GET":
            form = OfflineModelForm(instance=offlineModel)
            try:
                offlineModelLabels = json.loads(offlineModel.offline_model_labels)
            except Exception as e:
                offlineModelLabels = []
            return render(request,"offline_model/create.html",{'form':form, 'offlineModel':offlineModel,'offlineModelLabels':offlineModelLabels})
        elif request.method == "POST":
            form = OfflineModelForm(request.POST or None, request.FILES or None, instance=offlineModel)
            if form.is_valid():
                if request.FILES.get('file', False):
                    try:
                        if not os.path.exists(offlineModelFile):
                            os.remove(os.environ.get('PROJECT_FOLDER','') + '/' + offlineModelFile)
                        else:
                            os.remove(offlineModelFile)
                    except Exception as e:
                        print('Failed to remove old Offline Model File: ' + str(offlineModelFile))
                        messages.info(request, 'Failed to remove old Offline Model File')

                instance = form.save(commit=False)
                instance.offline_model_labels = json.dumps(request.POST.getlist('offline_model_labels'))
                instance.save()
                messages.success(request, "Offline Model Updated Successfully!")
            else:
                messages.error(request, "Invalid Request")
                return render(request,"offline_model/create.html",{'form':form, 'offlineModel':offlineModel})

        return redirect("offline.model.list")
    except(OfflineModel.DoesNotExist):
        messages.error(request, "Invalid Offline Model attempted to Edit")
        return redirect("offline.model.list")

#########################
# OFFLINE MODELS DELETE #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelDelete(request, id):
    try:
        if request.method == "POST":
            if request.user.user_type == 'project_admin':
                offlineModel = OfflineModel.objects.filter(id=id).filter(created_by=request.user).get()
            else:
                offlineModel = OfflineModel.objects.filter(id=id).get()
            offlineModel.file.delete()
            offlineModel.delete()
            messages.success(request, 'Offline Model Deleted Successfully!')
            return redirect('offline.model.list')
        else:
            messages.error(request, 'Failed to Delete!')
            return redirect('offline.model.list')
    except(OfflineModel.DoesNotExist):
        messages.error(request, "Invalid Offline Model attempted to Delete")
        return redirect("offline.model.list")

#############################################
# SHOW .py Offline Local Model Dependencies #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelDependencies(request, id):
    try:
        if request.method == "POST":
            if request.user.user_type == 'project_admin':
                offlineModel = OfflineModel.objects.filter(id=id).filter(created_by=request.user).get()
            else:
                offlineModel = OfflineModel.objects.filter(id=id).get()
            saved_model = None
            if not os.path.exists(os.path.join('media/offline_models/')):
                saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+offlineModel.filename()
            else:
                saved_model = os.path.join('media/offline_models/', offlineModel.filename())
            
            if offlineModel.model_format in ('py') and saved_model:
                import importlib, inspect
                loader = importlib.machinery.SourceFileLoader('model', saved_model)
                handle = loader.load_module('model')
                deps = ', '.join(str(i[0]) for i in inspect.getmembers(handle, inspect.ismodule ))
                if 'model' in sys.modules:  
                    del sys.modules["model"]
                return JsonResponse({'message':'Dependencies Loaded', 'data':deps}, status=200)
            else:
                return JsonResponse({'message':'Invalid Type (Dependencies can be checked only with py format)'}, status=404)
        else:
            return JsonResponse({'message':'Invalid Request'}, status=404)
    except(OfflineModel.DoesNotExist):
        return JsonResponse({'message':'Offline Model Not Found'}, status=404)
    except Exception as e:
        return JsonResponse({'message':'Failed to Check Dependencies'}, status=500)

########################
# OFFLINE MODELS TEST #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelTest(request, id):
    try:
        if request.user.user_type == 'project_admin':
            offlineModel = OfflineModel.objects.filter(id=id).filter(created_by=request.user).get()
        else:
            offlineModel = OfflineModel.objects.filter(id=id).get()
        
        if request.method == "POST":
            if offlineModel.preprocess or offlineModel.postprocess:
                quick_test_image_result = quick_test_offline_image_pre_post(request.FILES.get('file', False), offlineModel, request, fake_score=request.POST.get('fake_score', 0), fake_result=request.POST.get('fake_result', ""), direct_offline_model=True)
                if quick_test_image_result:
                    if offlineModel.preprocess:
                        request.session['image'] = quick_test_image_result.get('image',False)
                    else:
                        request.session['test_result'] = json.dumps(quick_test_image_result.get('data','No Test Data'), indent=4)
                else:
                    messages.error(request, 'Unable to Test. Pre-Process / Post-Process failed or did not return a result.')
                
                return redirect('offline.model.test', id=id)
                
            quick_test_image_result = quick_test_offline_image(request.FILES.get('file', False), offlineModel, direct_offline_model=True)
            if quick_test_image_result:
                request.session['test_result'] = json.dumps(quick_test_image_result.get('data','No Test Data'), indent=4)
                messages.success(request, 'Score: '+str(quick_test_image_result.get('score','0'))+' | Class: '+str(quick_test_image_result.get('result','Not Found')))
            else:
                messages.error(request, 'Unable to Test (Either Offline Model did not work correctly or response was incorrect.)')

            return redirect('offline.model.test', id=id)
        elif(request.method == "GET"):
            test_result = request.session.pop('test_result', False)
            image = request.session.pop('image', False)
            return render(request, 'offline_model/test.html', {'model':offlineModel, 'test_result':test_result, 'image':image})
        else:
            messages.error(request, 'Failed to Test!')
            return redirect('offline.model.list')
    except(OfflineModel.DoesNotExist):
        messages.error(request, "Invalid Offline Model attempted to Test")
        return redirect("offline.model.list")

###########################################
# View Readme md file from /api/README.md #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def offlineModelReadme(request):
    return markdownToHtml(request, 'api/README.md', 'README.md - Offline Model & API')

#########################
# Clean Temporary Files #
@user_passes_test(is_admin, login_url=login_url)
def cleanTemp(request):
    files = []
    if not os.path.exists(os.path.join('media/temp/')):
        files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/temp/*')
    else:
        files = glob.glob(os.path.join('media/temp/*'))
    count = 0
    for f in files:
        if "temp" in f:
            os.remove(f)
            count += 1

    if request.GET.get('all', False):
        # CLEAN /media/image/* - ALL IMAGE FILES THAT MAY NOT HAVE BEEN CLEANED by bugs
        image_file_names = []
        for name in ImageFile.objects.values_list('file', flat=True):
            image_file_names.append(re.sub("(.*[\\/])+", "", name))
        # print(image_file_names)
        # ---
        foldered_image_file_names = []
        if not os.path.exists(os.path.join('media/image/')):
            image_files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/image/*')
        else:
            image_files = glob.glob(os.path.join('media/image/*'))
        for f in image_files:
            foldered_image_file_names.append(re.sub("(.*[\\/])+", "", str(f)).split("\\")[-1])
        # print(foldered_image_file_names)
        print('DIFFERENCES:')
        differences = set(foldered_image_file_names) - set(image_file_names)
        print(differences)
        for imposter_image in differences:
            if not os.path.exists(os.path.join('media/image/')):
                os.remove(os.environ.get('PROJECT_FOLDER','') + '/media/image/' + imposter_image)
            else:
                os.remove(os.path.join('media/image/', imposter_image))
            count += 1

    messages.success(request, str(count)+' Temporary File(s) removed')
    reload_classifier_list()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER','/dashboard'))

#################################
# Clean Street View Saved Images #
@user_passes_test(is_admin, login_url=login_url)
def cleanTempStreetView(request):
    files = []
    if not os.path.exists(os.path.join('media/street_view_images/')):
        files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/street_view_images/*')
    else:
        files = glob.glob(os.path.join('media/street_view_images/*'))
    count = 0
    for f in files:
        if "street_view_images" in f:
            os.remove(f)
            count += 1
    messages.success(request, str(count)+' Saved Street View Images removed')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

#########################
# Count Total Image Files #
@user_passes_test(is_admin, login_url=login_url)
def countImage(request):
    files = []
    if not os.path.exists(os.path.join('media/image/*')):
        files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/image/*')
    else:
        files = glob.glob(os.path.join('media/image/*'))
    count = 0
    for f in files:
        count += 1
    messages.success(request, str(count)+' Image File(s) exists in total')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

##########################
# Dump JSON of all Image #
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def dumpImage(request):
    try:
        if(is_admin(request.user)):
            images = Image.objects.order_by('-created_at').all().prefetch_related('image_files')
        elif(is_project_admin(request.user)):
            projects = Projects.objects.filter(users__id=request.user.id)
            images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).order_by('-created_at').prefetch_related('image_files').distinct()
        # messages.success(request, 'Image & Image File data dumped')
        data = {'data': [], 'status': 'success', 'dumped_at': datetime.today().strftime('%Y-%m-%d-%H:%M:%S'), 'dumped_by': request.user.full_name}
        for i in images:
            this_image = {
                'id': str(i.id),
                'title': str(i.title),
                'description': str(i.description),
                'user_id': str(i.user.id),
                'user_name': str(i.user.full_name),
                'lat': str(i.lat),
                'lng': str(i.lng),
                'created_at': str(i.created_at),
                'updated_at': str(i.updated_at),
                'image_files': [],
            }
            for j in i.image_files.all():
                this_image['image_files'] = this_image['image_files'] + [{
                    'file': 'http://'+request.get_host()+str(j.file.url),
                    'tested': str(j.tested).lower(),
                    'result': str(j.result),
                    'score': str(j.score),
                    'object_type': str(j.object_type),
                    'retrained': str(j.retrained).lower(),
                    'verified': str(j.verified).lower(),
                    'created_at': str(j.created_at),
                    'updated_at': str(j.updated_at),
                }]

            data['data'] = data['data'] + [this_image]
            # print(data)
        response = HttpResponse(json.dumps(data, indent=4), content_type="application/json")
        response['Content-Disposition'] = 'attachment; filename=' + 'image_and_image_files_dump_' + datetime.today().strftime('%Y-%m-%d-%H:%M:%S') + '.json'
        return response
        # return JsonResponse(data, safe=True)
    except Exception as e:
        print(e)
        messages.error(request,'Failed to Dump & Download Image and Image File Data')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

########################
# RUN TERMINAL COMMAND #
########################
@user_passes_test(is_admin, login_url=login_url)
def terminal(request):
    cmd_list = [
        'pip install', 'pip --version', 'python --version', 'pip list', 'ls', 'server.log'
        # 'server.up', 'server.down',
    ]
    if not settings.PRODUCTION:
        cmd_list.append('dir')

    if request.method == "GET":
        return render(request, 'terminal.html', {'cmd_list':cmd_list})
    elif request.method == "POST" and request.POST.get('cmd', False):
        print('User id ' + str(request.user.id) + ' - ' + str(request.user.full_name) + ' accessed the terminal')
        cmd = request.POST.get('cmd','')
        # Split multiline to single line
        cmd = cmd.splitlines()[0]
        # Multiple command split to single
        cmd = cmd.split('||')[0]
        cmd = cmd.split('&&')[0]
        cmd = cmd.split(';')[0]
        cmd = cmd.strip()

        # Check cmd_list pass
        cmd_list_pass = cmd.startswith(tuple(cmd_list))

        # Special Commands
        original_cmd = cmd
        if cmd == 'server.log':
            cmd = "tail -n 250 /var/log/messages | grep 'gunicorn\|python3'"

        res = ''
        err = ''
        if cmd_list_pass:
            try:
                if not settings.PRODUCTION:
                    output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
                else: # GO INTO THE vitual env and call cmd
                    project_root = os.environ.get('PROJECT_FOLDER','/')
                    output = subprocess.run(('cd ' + project_root + ' && . env/bin/activate && '+cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True, cwd='/')
                
                res = re.sub("(.+)( [^ ]+ gunicorn)", r"<b>\1</b>", str(output.stdout))
                err = str(output.stderr)
            except Exception as e:
                print('-FAILURE RUNNING TERMINAL COMMAND-')
                print(e)
                return JsonResponse({"message":"Unable to run the provided command. Server Error."}, status=500)
        else:
            return JsonResponse({"message":"Invalid Command Provided"}, status=404)

        return JsonResponse({"cmd":original_cmd, "res":res, "err":err}, status=200)
    else:
        return JsonResponse({"message":"Invalid Request"}, status=404)

# FILE UPLOAD
# Add Image via Dashboard
@user_passes_test(is_admin, login_url=login_url)
def fileUpload(request):
    if request.method == "GET":
        form = FileUploadForm()
        file_uploads = FileUpload.objects.all()
        return render(request,"file_upload.html",{'form':form, 'file_uploads': file_uploads})
    elif request.method == "POST":
        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # EDIT
            try:
                fileUpload = FileUpload.objects.filter(id=request.POST.get('id')).get()
                # DELETE OLD FILE IF NEW EXISTS
                if request.FILES.get('file', False):
                    fileUpload.file.delete()
                form = FileUploadForm(request.POST or None, request.FILES or None, instance=fileUpload)
                if form.is_valid():
                    instance = form.save(commit=False)
                    instance.save()
                    messages.success(request, "File Updated Successfully")
                    return redirect("file_upload")
            except(FileUpload.DoesNotExist):
                pass
        else:
            # Create
            form = FileUploadForm(request.POST or None, request.FILES or None)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.created_by = request.user
                instance.save()
                messages.success(request, "File Uploaded Successfully")
                return redirect("file_upload")

    messages.error(request, "Invalid Request")
    return redirect("file_upload")

@user_passes_test(is_admin, login_url=login_url)
def fileUploadDelete(request, id):
    if request.method == "POST":
        try:
            fileUpload = FileUpload.objects.filter(id=id).get()
            fileUpload.file.delete()
            fileUpload.delete()
            messages.success(request, 'File Deleted Successfully!')
            return redirect("file_upload")
        except(FileUpload.DoesNotExist):
            pass

    messages.error(request, "Invalid Request")
    return redirect("file_upload")

#######
# API #
#######

# Images API
class ImageView(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [AllowAny]
    # permission_classes = [IsAdminUser]

    # TO LIMIT WHAT USER CAN DO - EDIT,SEE,DELETE
    def get_queryset(self):
        if self.action == 'list':
            page = abs(int(self.request.GET.get('page', 1)))
            offset = 25 * (page - 1)
            limit = 25
            offsetPlusLimit = offset + limit
            if self.request.user.is_authenticated:
                if self.request.user.is_admin:
                    ids = Image.objects.order_by('-created_at').values_list('pk', flat=True)[offset:offsetPlusLimit] # Latest 25
                    return Image.objects.filter(pk__in=list(ids)).order_by('-created_at')
                elif self.request.user.is_project_admin:
                    projects = Projects.objects.filter(users__id=self.request.user.id)
                    ids = Image.objects.filter(Q(user_id=self.request.user.id) | Q(project__in=projects)).order_by('-created_at').distinct()[offset:offsetPlusLimit] # Latest 25
                    return Image.objects.filter(pk__in=list(ids)).order_by('-created_at')
                else:
                    ids = Image.objects.filter(user_id=self.request.user.id).order_by('-created_at')[offset:offsetPlusLimit] # Latest 25
                    return Image.objects.filter(pk__in=list(ids)).order_by('-created_at')
            else:
                return []
        else:
            if self.request.user.is_authenticated:
                if self.request.user.is_admin:
                    return Image.objects.order_by('-created_at')
                elif self.request.user.is_project_admin:
                    projects = Projects.objects.filter(users__id=self.request.user.id)
                    return Image.objects.filter(Q(user_id=self.request.user.id) | Q(project__in=projects)).order_by('-created_at').distinct()
                else:
                    return Image.objects.filter(user_id=self.request.user.id).order_by('-created_at')
            else:
                return []

    # TO LIMIT PERMISSION - I CREATED CUSTOM PERMISSION IN main/authorization.py
    # Files contains checker for Authorization as well as passes test
    # def get_permissions(self):
    #     if self.action == 'list':
    #         self.permission_classes = [HasAdminPermission, ]
    #     elif self.action == 'retrieve':
    #         self.permission_classes = [HasAdminPermission]
    #     return super(self.__class__, self).get_permissions()

    def destroy(self, request, *args, **kwargs):
        image = self.get_object()
        for i in image.image_files.all():
            i.file.delete()
            i.delete()
        return super().destroy(request, *args, **kwargs)

class VideoFrameView(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = VideoFrameSerializer
    http_method_names = ['post', 'head', 'options']
    permission_classes = [AllowAny]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.request.user.is_admin:
                return Image.objects.order_by('-created_at').all()[:25] # Latest 25
            elif self.request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=self.request.user.id)
                return Image.objects.filter(Q(user_id=self.request.user.id) | Q(project__in=projects)).order_by('-created_at').distinct()[:25] # Latest 25
            else:
                return Image.objects.filter(user_id=self.request.user.id).order_by('-created_at')[:25] # Latest 25
        else:
            return []

    def destroy(self, request, *args, **kwargs):
        image = self.get_object()
        for i in image.image_files.all():
            i.file.delete()
            i.delete()
        return super().destroy(request, *args, **kwargs)

class UserView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        if(self.request.method == "POST"):
            return User.objects.exclude(active__in=[True,False])

        if self.request.user.is_admin:
            return User.objects.all().order_by('-timestamp', '-active').prefetch_related(
                Prefetch(
                    "projects",
                    queryset=Projects.objects.all(),
                    to_attr="visible_projects"
                )
            )
        elif self.request.user.is_project_admin:
            return User.objects.exclude(user_type='admin').order_by('-timestamp', '-active').prefetch_related(
                Prefetch(
                    "projects",
                    queryset=Projects.objects.filter(users__id=self.request.user.id).distinct(),
                    to_attr="visible_projects"
                )
            )
        else:
            return User.objects.filter(id=self.request.user.id).prefetch_related(
                Prefetch(
                    "projects",
                    queryset=Projects.objects.filter(users__id=self.request.user.id).distinct(),
                    to_attr="visible_projects"
                )
            )

    def get_permissions(self):
        if self.action == 'list':
            self.permission_classes = [HasAdminOrProjectAdminPermission]
        elif self.action == 'retrieve':
            self.permission_classes = [IsAuthenticated]
        elif self.action == 'create':
            if self.request.user.is_project_admin:
                self.permission_classes = [HasProjectAdminPermission]
            elif self.request.user.is_admin:
                self.permission_classes = [HasAdminPermission]
            else:
                self.permission_classes = [HasGuestPermission]
        elif self.action == 'update':
            if self.request.user.is_project_admin:
                self.permission_classes = [HasProjectAdminPermission]
            elif self.request.user.is_admin:
                self.permission_classes = [HasAdminPermission]
            else:
                self.permission_classes = [IsAuthenticated]
        elif self.action == 'partial_update':
            if self.request.user.is_project_admin:
                self.permission_classes = [HasProjectAdminPermission]
            elif self.request.user.is_admin:
                self.permission_classes = [HasAdminPermission]
            else:
                self.permission_classes = [IsAuthenticated]
        elif self.action == 'destroy':
            self.permission_classes = [HasAdminPermission]
        return super(self.__class__, self).get_permissions()

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if(user.image != 'user_images/default.png'):
            user.image.delete()
        return super().destroy(request, *args, **kwargs)

class ProfileView(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    http_method_names = ['get']
    permission_classes = [AllowAny]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    def list(self, request, *args, **kwargs):
        user = User.objects.filter(id=self.request.user.id).first()
        if not user:
            fake_user = User.objects.first()
            object_types = []
            projects = []
            if fake_user:
                object_types = fake_user.get_object_detect_json(request)
                projects = fake_user.get_project_json(request)
            
            return Response({
                "id": 0,
                "full_name": "Guest",
                "email": "Guest",
                "user_type": "Guest",
                "image": request.scheme + '://' + request.META['HTTP_HOST'] + '/media/user_images/default.png',
                "projects": projects,
                "object_types": object_types,
            })
        else:
            return Response({
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "user_type": user.user_type,
                "image": request.scheme + '://' + request.META['HTTP_HOST'] + user.image.url,
                "projects": user.get_project_json(request),
                "object_types": user.get_object_detect_json(request),
            })

def get_jwt_claims(request):
    from rest_framework_simplejwt.state import token_backend
    from rest_framework_simplejwt.authentication import JWTAuthentication
    try:
        jwt = JWTAuthentication()
        header = jwt.get_header(request=request)
        raw_token = jwt.get_raw_token(header)
        return token_backend.decode(token=raw_token)
    except:
        return {}

@api_view()
def test_view(request):
    results = TestSerializer({'ping':'pong'}).data
    return Response(results)

class ProjectView(viewsets.ModelViewSet):
    queryset = Projects.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # reload_classifier_list()
        # PUBLIC PROJECTS ONLY
        if self.action == 'list' and self.request.GET.get('public', False) == 'true':
            projects_list = []
            query = self.request.GET.get('q','')
            joined = self.request.GET.get('joined',False)

            projects_list = Projects.objects.order_by('-updated_at')

            # FILTER AND SHOW ONLY JOINED
            if joined == 'true':
                projects_list = projects_list.filter(Q(users__id=self.request.user.id))
            # ELSE ALL
            else:
                projects_list = projects_list.filter(Q(public=True) | Q(users__id=self.request.user.id))

            # IF SEARCH
            if query and len(query) > 0:
                projects_list = projects_list.filter(Q(project_name__icontains=query) |
                                                    Q(project_desc__icontains=query) |
                                                    Q(object_types__name__icontains=query))
            
            projects_list = projects_list.distinct().all()
            paginator = Paginator(projects_list, 25)  # Show 25
            page_number = self.request.GET.get('page', '1')
            projects_list = paginator.get_page(page_number)
            return projects_list

        # ALL PROJECTS
        if self.request.user.is_authenticated:
            if self.request.user.is_admin:
                return Projects.objects.all().order_by('project_name')
            elif self.request.user.is_project_admin:
                return Projects.objects.filter(users__id=self.request.user.id).order_by('project_name')
        
        return []

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        project.image.delete()
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['POST'])
    def test(self, request, pk=None, *args, **kwargs):
        # Request Body: 
        # file = Image file to test
        if not request.FILES.get('file', False):
            test_result = {'message': 'Test Image not provided.'}
            return JsonResponse(test_result, status=404)

        try:
            project = Projects.objects.get(pk=pk)
        except:
            test_result = {'message': 'Invalid Project'}
            return JsonResponse(test_result, status=404)

        if os.environ.get('PROJECT_FOLDER',False):
            project_folder = os.environ.get('PROJECT_FOLDER','') + '/'
        else:
            project_folder = ''

        # IF THIS PROJECT HAS OFFLINE MODEL THEN
        if project.offline_model:
            quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.offline_model, offline=True, project_folder=project_folder, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())
        # ELSE ONLINE MODEL THEN
        else:
            quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.detect_model, offline=False, project_folder=project_folder, ibm_api_key=project.ibm_api_key, ibm_service_url=project.get_ibm_service_url())
        
        test_result = None
        if quick_test_image_result:
            test_result = quick_test_image_result
        
        if test_result:
            # print(type(test_result))
            return JsonResponse(test_result, status=200, safe=False)

        test_result = {'message': 'Test Failed. Either No Object Was Detected or the model is not in ready state.'}
        return JsonResponse(test_result, status=404)
    
    @action(detail=True, methods=['POST'])
    def join(self, request, pk=None, *args, **kwargs):
        try:
            project = Projects.objects.filter(public=True).get(id=pk)
            request.user.projects.add(project)
            return JsonResponse({'message':'Project Joined Successfully'}, status=200)
        except(Projects.DoesNotExist):
            return JsonResponse({'message':'Invalid Project'}, status=404)

    @action(detail=True, methods=['POST'])
    def leave(self, request, pk=None, *args, **kwargs):
        try:
            project = Projects.objects.get(id=pk)
            request.user.projects.remove(project)
            return JsonResponse({'message':'Project Left Successfully'}, status=200)
        except(Projects.DoesNotExist):
            return JsonResponse({'message':'Invalid Project'}, status=404)

class ObjectTypeView(viewsets.ModelViewSet):
    queryset = ObjectType.objects.all()
    serializer_class = ObjectTypeSerializer
    permission_classes = [HasAdminOrProjectAdminPermission]

    def get_queryset(self):
        # reload_classifier_list()
        if self.request.user.is_authenticated:
            if self.request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=self.request.user.id)
                return ObjectType.objects.filter(Q(created_by=self.request.user) | Q(project__in=projects)).order_by('-created_at').order_by('project').all()
            elif self.request.user.is_admin:
                return ObjectType.objects.order_by('-created_at').order_by('project').all()
        
        return []

    def destroy(self, request, *args, **kwargs):
        object_type = self.get_object()
        if(object_type.image != 'object_types/default.jpg'):
            object_type.image.delete()
        return super().destroy(request, *args, **kwargs)

@api_view(http_method_names=["POST"])
def terminal_view(request):
    if request.user and request.user.is_admin:
        return terminal(request)
    return Response({"message":"Unauthorized Terminal Access"})

@api_view(http_method_names=["POST"])
def clean_temp_view(request):
    if request.user and request.user.is_admin:
        files = []
        count = 0
        if not os.path.exists(os.path.join('media/temp/')):
            files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/temp/*')
        else:
            files = glob.glob(os.path.join('media/temp/*'))
        for f in files:
            if "temp" in f:
                os.remove(f)
                count += 1
        if not os.path.exists(os.path.join('media/street_view_images/')):
            files = glob.glob(os.environ.get('PROJECT_FOLDER','') + '/media/street_view_images/*')
        else:
            files = glob.glob(os.path.join('media/street_view_images/*'))
        for f in files:
            if "street_view_images" in f:
                os.remove(f)
                count += 1
        reload_classifier_list()
        return Response({"message": str(count)+" Temporary Images Removed"})
    return Response({"message":"Unauthorized Access"}, status=403)

class FileUploadView(viewsets.ModelViewSet):
    queryset = FileUpload.objects.all()
    serializer_class = FileUploadSerializer
    permission_classes = [HasAdminPermission]

    def destroy(self, request, *args, **kwargs):
        fileUpload = self.get_object()
        fileUpload.file.delete()
        return super().destroy(request, *args, **kwargs)

class ClassifierView(viewsets.ModelViewSet):
    queryset = Classifier.objects.all()
    serializer_class = ClassifierSerializer
    permission_classes = [HasAdminOrProjectAdminPermission]

    def get_queryset(self):
        # reload_classifier_list()
        if self.request.user.is_authenticated:
            if self.request.user.is_admin:
                if self.request.GET.get('object_type', False):
                    return Classifier.objects.order_by('-object_type','order').filter(object_type=self.request.GET.get('object_type')).all()
                else:
                    return Classifier.objects.order_by('-object_type','order').all()
            elif self.request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=self.request.user.id)
                if self.request.GET.get('object_type', False):
                    return Classifier.objects.order_by('-object_type','order').filter(Q(created_by=self.request.user) | Q(project__in=projects)).filter(object_type=self.request.GET.get('object_type')).all()
                else:
                    return Classifier.objects.order_by('-object_type','order').filter(Q(created_by=self.request.user) | Q(project__in=projects)).all()
        
        return []

    def destroy(self, request, *args, **kwargs):
        classifier = self.get_object()
        object_type = classifier.object_type
        object_type.verified = False
        object_type.save()
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['POST'])
    def order(self, request, *args, **kwargs):
        # Request Body: 
        # object_type_id = Object Type Id to Sort/Order Classifier for
        # classifiers = json string '[4,2,5]' with ids of classifier
        classifier_ids = json.loads(request.POST.get('classifiers','[]'))
        projects = Projects.objects.filter(users__id=request.user.id)
        object_type_id = request.POST.get('object_type_id',0)
        error = 0
        for idx, classifier_id in enumerate(classifier_ids):
            try:
                if request.user.user_type == 'project_admin':
                    classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).filter(object_type=object_type_id).get(id=classifier_id)
                else:
                    classifier = Classifier.objects.filter(object_type=object_type_id).get(id=classifier_id)
                classifier.order = idx + 1
                classifier.save()
                # THEN reset verified to False
                object_type = ObjectType.objects.filter(id=object_type_id).get()
                object_type.verified = False
                object_type.save()
            except(Classifier.DoesNotExist):
                error = error + 1
        
        res = {'message': 'Classifier Order Updated', 'errors': error}
        return JsonResponse(res, status=200)

    @action(detail=True, methods=['POST'])
    def test(self, request, pk=None, *args, **kwargs):
        # Body:
        # file = image file to test on
        # URL Prams:
        # :id = id of classifier
        try:
            if request.user.user_type == 'project_admin':
                projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').all()
                classifier = Classifier.objects.filter(Q(created_by=request.user) | Q(project__in=projects)).get(id=pk)
            else:
                classifier = Classifier.objects.get(id=pk)

            res = {}
            # IF THIS CLASSIFIER HAS OFFLINE MODEL THEN
            if classifier.offline_model:
                # IF IS A PRE / POST TEST
                if classifier.offline_model.preprocess or classifier.offline_model.postprocess:
                    quick_test_image_result = quick_test_offline_image_pre_post(request.FILES.get('file', False), classifier, request, fake_score=request.POST.get('fake_score', 0), fake_result=request.POST.get('fake_result', ""))
                    if quick_test_image_result:
                        if classifier.offline_model.preprocess:
                            res['image'] = quick_test_image_result.get('image',False)
                        else:
                            res['test_result'] = quick_test_image_result.get('data',{})
                        
                        return JsonResponse(res, status=200)
                    else:
                        res['message'] = 'Unable to Test. Pre-Process / Post-Process failed or did not return a result.'
                        return JsonResponse(res, status=400)
                    
                quick_test_image_result = quick_test_offline_image(request.FILES.get('file', False), classifier)
            # IF ONLINE MODEL which is_object_detection
            elif classifier.is_object_detection:
                if os.environ.get('PROJECT_FOLDER',False):
                    project_folder = os.environ.get('PROJECT_FOLDER','') + '/'
                else:
                    project_folder = ''
                quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), classifier.name, offline=False, project_folder=project_folder, ibm_api_key=classifier.ibm_api_key, ibm_service_url=classifier.get_ibm_service_url())
                if quick_test_image_result:
                    res['test_result'] = quick_test_image_result
                    return JsonResponse(res, status=200)
            # ELSE ONLINE MODEL THEN
            else:
                quick_test_image_result = quick_test_image(request.FILES.get('file', False), classifier.name, classifier)
            
            if quick_test_image_result:
                res['test_result'] = quick_test_image_result.get('data',{})
                # res['score'] = quick_test_image_result.get('score','0')
                # res['result'] = quick_test_image_result.get('result','')
                return JsonResponse(res, status=200)
            else:
                return JsonResponse({'message':'Unable to Test (Make sure Classifier is valid and is in ready state)'}, status=200)
        except(Classifier.DoesNotExist):
            return JsonResponse({'message': 'Invalid Classifier'}, status=404)
        except Exception as e:
            print(e)
            return JsonResponse({'message': 'An Error Occurred'}, status=404)

class OfflineModelView(viewsets.ModelViewSet):
    queryset = OfflineModel.objects.all()
    serializer_class = OfflineModelSerializer
    permission_classes = [HasAdminOrProjectAdminPermission]

    def get_queryset(self):
        # reload_classifier_list()
        if self.request.user.is_authenticated:
            if self.request.user.is_admin:
                return OfflineModel.objects.all().order_by('name')
            elif self.request.user.is_project_admin:
                return OfflineModel.objects.filter(created_by=self.request.user).order_by('name')
        return []

    def destroy(self, request, *args, **kwargs):
        offline_model = self.get_object()
        offline_model.file.delete()
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['POST'])
    def dependencies(self, request, pk=None, *args, **kwargs):
        return offlineModelDependencies(request, pk)

    @action(detail=True, methods=['POST'])
    def test(self, request, pk=None, *args, **kwargs):
        # Body:
        # file = image file to test on
        # URL Prams:
        # :id = id of classifier
        try:
            if request.user.user_type == 'project_admin':
                offlineModel = OfflineModel.objects.filter(id=pk).filter(created_by=request.user).get()
            else:
                offlineModel = OfflineModel.objects.filter(id=pk).get()

            res = {}
            if offlineModel.preprocess or offlineModel.postprocess:
                quick_test_image_result = quick_test_offline_image_pre_post(request.FILES.get('file', False), offlineModel, request, fake_score=request.POST.get('fake_score', 0), fake_result=request.POST.get('fake_result', ""), direct_offline_model=True)
                if quick_test_image_result:
                    if offlineModel.preprocess:
                        res['image'] = quick_test_image_result.get('image',False)
                    else:
                        res['test_result'] = quick_test_image_result.get('data',{})
                    return JsonResponse(res, status=200)
                else:
                    res['message'] = 'Unable to Test. Pre-Process / Post-Process failed or did not return a result.'
                    return JsonResponse(res, status=400)
                
            quick_test_image_result = quick_test_offline_image(request.FILES.get('file', False), offlineModel, direct_offline_model=True)
            if quick_test_image_result:
                res['test_result'] = quick_test_image_result.get('data',{})
                return JsonResponse(res, status=200)
            else:
                res['message'] = 'Unable to Test (Either Offline Model did not work correctly or response was incorrect.)'
                return JsonResponse(res, status=400)

        except(OfflineModel.DoesNotExist):
            return JsonResponse({'message': 'Invalid Offline Model / Script'}, status=404)
        except Exception as e:
            print(e)
            return JsonResponse({'message': 'An Error Occurred'}, status=404)

@api_view(http_method_names=["GET","POST","OPTIONS"])
def fetch_classifier_detail(request):
    if not request.user.is_admin or not request.user.is_project_admin:
        return Response({"message":"Unauthorized Access"}, status=403)

    reload_classifier_list()
    authorized_classifier_list = {}
    projects = []
    if request.user.user_type == 'project_admin':
        projects = Projects.objects.filter(users__id=request.user.id).order_by('created_at').all().prefetch_related(Prefetch('object_types', queryset=ObjectType.objects.order_by('created_at').all().prefetch_related(Prefetch('classifiers', queryset=Classifier.objects.order_by('-object_type','order')))))
    else:
        projects = Projects.objects.order_by('created_at').all().prefetch_related(Prefetch('object_types', queryset=ObjectType.objects.order_by('created_at').all().prefetch_related(Prefetch('classifiers', queryset=Classifier.objects.order_by('-object_type','order')))))

    for project in projects:
        if not authorized_classifier_list.get(project.unique_name(), False):
            authorized_classifier_list[project.unique_name()] = {}

        if project.object_types.all().count():
            for object_type in project.object_types.all():
                if object_type.name.lower() not in authorized_classifier_list.get(project.unique_name(),[]):
                    authorized_classifier_list[project.unique_name()][object_type.name.lower()] = []
                
                if object_type.classifiers.all().count():
                    for classifier in object_type.classifiers.all():
                        if classifier.name not in authorized_classifier_list.get(project.unique_name(),[]).get(object_type.name.lower(),[]):
                            authorized_classifier_list[project.unique_name()][object_type.name.lower()] = authorized_classifier_list[project.unique_name()][object_type.name.lower()] + [classifier.name]
    
    if request.method == "GET":
        return Response({'data':authorized_classifier_list}, status=200)
    if request.method == "POST" and request.user:
        detail = classifier_detail(request.POST.get('project', False), request.POST.get('object', False), request.POST.get('model', False))
        if not detail:
            detail = {'message': 'Could Not Fetch Classifier Detail'}
            return Response(detail, status=404)
        return Response({'data':detail}, status=200)
        
    return Response({"message":"Unauthorized Access"}, status=403)

@api_view(http_method_names=["GET","POST","OPTIONS"])
def fetch_object_type_detail(request):
    reload_classifier_list()
    if request.method == "GET":
        default_object_model = classifier_list.detect_object_model_id
        if request.user.is_project_admin:
            projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name').values('id','detect_model','project_name','offline_model').distinct()
        else:
            projects = Projects.objects.all().values('id','detect_model','project_name','offline_model').distinct()
        return Response({'data':projects, 'default_object_model':default_object_model}, status=200)
    if request.method == "POST" and request.POST.get('object_id', False) and request.user and (request.user.is_admin or request.user.is_project_admin):
        detail = None
        object_id = request.POST.get('object_id', False)
        project = Projects.objects.get(id=object_id)
        
        # IF Watson Object Detail is a offline Model type
        if project.offline_model:
            offline_model = project.offline_model
            if offline_model:
                try:
                    offlineModelLabels = json.loads(offline_model.offline_model_labels)
                except Exception as e:
                    offlineModelLabels = []
                detail = {
                    'offline': True,
                    'name': offline_model.name,
                    'type': offline_model.model_type,
                    'format': offline_model.model_format,
                    'labels': offlineModelLabels,
                    'url': offline_model.file.url
                }
                return Response({'data':detail, 'object_id':offline_model.name}, status=200)
        
        # If not offline model try online
        try:
            detail = object_detail(project.detect_model, project.ibm_api_key, project.get_ibm_service_url())
            if detail:
                return Response({'data':detail, 'object_id':object_id}, status=200)
            else:
                detail = {'message':'Could Not Fetch List Object Detail Metadata'}
                return Response(detail, status=404)
        except:
            detail = {'message':'Could Not Fetch List Object Detail Metadata (Server Error or Object Not Found)'}
            return Response(detail, status=404)
        
    return Response({"message":"Unauthorized or Invalid Request"}, status=403)

@api_view(http_method_names=["POST","OPTIONS"])
def retrain_classifier(request):
    if request.method == "POST" and request.user and (request.user.is_admin or request.user.is_project_admin):
        # images = multiple images list
        # project = project value from GET Classifier Details
        # object = object value from GET Classifier Details
        # model = model value from GET Classifier Details | or "all" to re-train on all online models
        # result = result to re-train on go,nogo,negative etc.
        # process = Process the images
        # rotate = Rotate the images
        # warp = warp the images
        # inverse = inverse negative the images
        zipped = 0
        image_file_list = []
        for image in request.FILES.getlist('images'):
            kind = filetype.guess(image)
            if kind is None:
                print('Cannot guess file type! - API')
            else:
                filename = '{}.{}'.format(uuid.uuid4().hex, kind.extension)
                destination = open(settings.MEDIA_ROOT + '/temp/' + filename, 'wb+')
                for chunk in image.chunks():
                    destination.write(chunk)
                destination.close()
                if not os.path.exists(os.path.join('media/temp/')):
                    image_file_list = image_file_list + [os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename]
                else:
                    image_file_list = image_file_list + [os.path.join('media/temp/', filename)]
                zipped += 1
                # print(image_file_list)

        min_image_required = 10
        msg = ''
        ok = False
        if settings.DEBUG:
            min_image_required = 2

        # we have "model" in request. If Model is 'all' or not provided then all images are re-trained in 'all' classifiers of object type given, else only on selected classifier (it is the last parameter in retrain function)
        if zipped >= min_image_required and image_file_list and request.POST.get('project', False) and request.POST.get('object', False) and request.POST.get('result', False):
            retrain_status = retrain_image(image_file_list, request.POST.get('project'), request.POST.get('object').lower(), request.POST.get('result').lower(), 'temp', request.POST.get('model', False), request.POST.get('process', False), request.POST.get('rotate', False), request.POST.get('warp', False), request.POST.get('inverse', False), request=request)
            print(retrain_status)
            if retrain_status:
                msg = str(zipped) + ' images zipped and was sent to retrain in ' + str(retrain_status) + ' classifier(s). (Retraining takes time)'
                ok = True
            else:
                msg = str(zipped) + ' images zipped but failed to retrain'
        else:
            msg = str(zipped) + ' valid Image(s). At least 10 required. Or Invalid input.'

        print(str(len(image_file_list)) + ' original images uploaded re-train classifier API route...')
        for image_file in image_file_list:
            os.remove(image_file)
            pass

        reload_classifier_list()
        if ok:
            return Response({'message':msg}, status=200)
        else:
            return Response({'message':msg}, status=404)
        
    return Response({"message":"Unauthorized or Invalid Request"}, status=403)

# Setup Kobo Toolbox Guide:
# In your Kobo Rest Service use Endpoint URL:
# https://www.isac-simo.net/api/kobo/?token=<kobo_token>&domain=<kobo_domain>
# token = should be the Kobo Toolbox token that can be found in Account Settings
# domain = Domian that hosts kobo (defaults to https://kf.kobotoolbox.org/ with https://kc.kobotoolbox.org/ for update API)
# The domain value must be the one that supports Update API for /submissions.json
# ----------------
# The Form can contain multiple ISAC-SIMO test able image upload fields with respective result holding field.
# The Image Upload field that needs to be sent to ISAC-SIMO should have name is following format:
# Data Column Name: isac_image_xxxx
# Where xxxx should be unique identifier
# ----------------
# The Object Type / Check holding Select One Dropdown should have:
# Data Column Name: isac_object_xxxx
# ----------------
# The Result holding hidden field should have:
# Data Column Name: isac_result_xxxx
# xxxx in all field must be same for related photo.
# ----------------
# The test result can also be viewed in ISAC-SIMO Dashboard
# The Description field by default will be "KoboToolbox / ID"
@api_view(http_method_names=["POST","OPTIONS"])
@authentication_classes([])
@permission_classes([])
def kobo(request):
    print("KoboToolbox Webhook Received.")
    object_type_field_start_with = "isac_object"
    image_field_start_with = "isac_image"
    result_field_start_with = "isac_result"
    body = json.loads(request.body.decode('utf-8'))
    # print(body)
    domain = request.GET.get("domain", "https://kc.kobotoolbox.org")
    object_type_id = request.GET.get("object_type_id", None)
    token = request.GET.get("token", None)
    isac_token = request.GET.get("isac_token", None) # ISAC-SIMO JWT Token (Not Required if Global Guest Project)
    total_sent_to_isac_simo = 0
    isac_simo_api = "https://www.isac-simo.net/api/image/"
    if token:
        isac_simo_api = isac_simo_api + "?token=" + "Token " + token

    updated_form_values = {}

    # Cache and Ignore the Duplicate request
    if body.get("_id", None) and cache.get("kobo-"+str(body.get("_id"))):
        return JsonResponse({"message":"Duplicate Request Ignored"}, status=200)

    # _attachments exists in POST body
    if body.get("_attachments"):
        cache.set("kobo-"+str(body.get("_id")), True, 120)
        print("KoboToolbox Webhook Is Valid. Continue...")
        # Loop through all key, value in POST content
        for key, value in body.items():
            # print(key, value)
            # If POST field is isac_image_.... 
            if key.startswith(image_field_start_with):
                isac_image_id = key.replace(image_field_start_with, '') # END VALUE STRIP AND GET id (if exists)
                for image in body.get("_attachments"): # Loop through all attachments
                    if value in image.get("filename"): # If attachment filename contains value of key (i.e. file name)
                        image_url = image.get("download_url")
                        # image_url = urllib.parse.quote(image.get("download_url"), safe='~()*!.\'')

                        # Check if Object Type ID has been provided from the Single Choice Field isac_object_xxx
                        for _key, _value in body.items():
                            if _key == (object_type_field_start_with+isac_image_id) and _value: # Matched the xxx and has value chosen
                                object_type_id = _value
                                break
                        
                        if not object_type_id: # If Still Object Type not found (did not came from webhook) Ignore the image.
                            continue

                        geolocation = body.get("_geolocation", [None, None])
                        lat = geolocation[0]
                        lng = geolocation[1]
                        description = "KoboToolbox / " + str(body.get("_id", "N/A"))
                        # Call ISAC-SIMO API with image url
                        headers = {
                            "Accept": "application/json"
                        }
                        if isac_token:
                            headers["Authorization"] = "Bearer " + isac_token
                        res = requests.post(isac_simo_api, data = {
                            "description": description,
                            "lat": lat,
                            "lng": lng,
                            "image_url": image_url,
                            "object_type_id": object_type_id
                        }, headers = headers)
                        if res.status_code == 201 or res.status_code == "201" or res.status_code == 200 or res.status_code == "200":
                            # SET Kobo result field if it exists
                            if body.get(result_field_start_with+isac_image_id):
                                data = res.json()
                                if data.get("image_files") and len(data.get("image_files")) > 0:
                                    result = data.get("image_files")[0].get("result", "")
                                    score = data.get("image_files")[0].get("score", 0)
                                    # print(result, score)
                                    updated_form_values[result_field_start_with+isac_image_id] = result # Assign result field with isac-simo result (Note: updated_form_values is sent back to Fulcrum)

                            total_sent_to_isac_simo += 1;

        if total_sent_to_isac_simo > 0:
            # Combine Webhook form_values and updated_form_values
            uploading_form_values = body
            uploading_form_values = {**uploading_form_values, **updated_form_values}
            meta = { 
                "meta" : {
                    "instanceID": "uuid:" + str(uuid.uuid4()),
                    "deprecatedID": uploading_form_values.get("meta/instanceID")
                }
            }
            uploading_form_values = {**uploading_form_values, **meta}

            # print(updated_form_values)
            # print(uploading_form_values)
            
            # Get x form id.
            submission_id = uploading_form_values.get("_xform_id_string")
            
            # Delete Unwanted keys from submitting
            # temp_uploading_form_values = list(uploading_form_values.keys())
            # for k in temp_uploading_form_values:
            #     if k.startswith('_'):
            #         uploading_form_values.pop(k)
            
            # Delete Unwanted keys from submitting
            uploading_form_values.pop("_id")
            uploading_form_values.pop("_notes")
            uploading_form_values.pop("_validation_status")
            uploading_form_values.pop("_uuid")
            uploading_form_values.pop("_tags")
            uploading_form_values.pop("_submitted_by")
            uploading_form_values.pop("_xform_id_string")
            uploading_form_values.pop("_submission_time")
            uploading_form_values.pop("_attachments")
            uploading_form_values.pop("_geolocation")
            uploading_form_values.pop("_status")
            uploading_form_values.pop("__version__")
            uploading_form_values.pop("start")
            uploading_form_values.pop("end")
            uploading_form_values.pop("formhub/uuid")
            uploading_form_values.pop("meta/instanceID")

            # print("---")
            # print(uploading_form_values)

            # CALL FULCRUM API TO UPDATE id submission data
            url = domain + "/api/v1/submissions.json"
            payload = {
                "id": submission_id,
                "submission": uploading_form_values
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Token " + token
            }
            response = requests.request("POST", url, json=payload, headers=headers)
            # print(response.text)
            return JsonResponse({"message":"OK"}, status=200)
        
    return JsonResponse({"message":"No ISAC-SIMO Image Uploaded OR Object Type Id Provided"}, status=200)

# FULCRUM WEBHOOK
@api_view(http_method_names=["POST","OPTIONS"])
@authentication_classes([])
@permission_classes([])
def fulcrum(request):
    print("Fulcrum Webhook Received.")
    object_type_field_start_with = "isac_object"
    image_field_start_with = "isac_image"
    result_field_start_with = "isac_result"
    hook_data = json.loads(request.body.decode('utf-8'))
    event_type = hook_data.get("type", None)
    body = hook_data.get("data", None)
    # print(body)
    object_type_id = request.GET.get("object_type_id", None)
    token = request.GET.get("token", None) # Fulcrums Token
    isac_token = request.GET.get("isac_token", None) # ISAC-SIMO JWT Token (Not Required if Global Guest Project)
    total_sent_to_isac_simo = 0
    isac_simo_api = "https://www.isac-simo.net/api/image/"

    updated_form_values = {}
    # body exists in webhook data + event type is create event
    # + form_values exists in POST body + form_id (to fetch forms data) 
    # + token (Needed to generate Public Image URL)
    # + isac_token (Not Required, But can be used to authorize ISAC-SIMO API using Bearer Token generated from profile page)
    # print(hook_data)
    # print(body)
    # print(type(body))

    # Cache and Ignore the Duplicate request
    if body.get("id", None) and cache.get(body.get("id")):
        return JsonResponse({"message":"Duplicate Request Ignored"}, status=200)

    if body and event_type == "record.create" and body.get("form_values") and body.get("form_id") and token:
        cache.set(body.get("id"), True, 120)
        print("Fulcrum Webhook Is Valid. Continue...")
        # Fetch the Single Form Metadata + Schema
        url = "https://api.fulcrumapp.com/api/v2/forms/"+body.get("form_id")+".json"
        querystring = {"schema":"true"}
        headers = {
            "Accept": "application/json",
            "X-ApiToken": token
        }
        res = requests.request("GET", url, headers=headers, params=querystring)
        # print(res)
        if res.status_code == 200 or res.status_code == "200":
            form = res.json() # Gets the Form Schema with "elements", "name", "image" etc.
            # print(form)
            if form and form.get("form") and form.get("form").get("elements"):
                elements = form.get("form").get("elements")
                # Loop through all key, value in elements array (contains keys like; type, key, label, data_name, required, hidden, disabled etc.)
                for element in elements:
                    # print(element)
                    # If element.data_name field starts with isac_image_.... and element.type is PhotoField
                    # Then, it probably is isac-simo testable uploaded image (So, we search for it in webhooks POST data form_values key)
                    if element.get("data_name").startswith(image_field_start_with) and element.get("type") == "PhotoField":
                        element_key = element.get("key")
                        isac_image_id = element.get("data_name").replace(image_field_start_with, '') # END VALUE STRIP AND GET id (if exists)
                        object_type_element_key = None
                        # Try to Search for isac_object_xxx and if found test the image... else ignore.
                        for object_type_element in elements:
                            # Comes from choice field.
                            if object_type_element.get("data_name") == (object_type_field_start_with+isac_image_id) and object_type_element.get("type") == "ChoiceField":
                                object_type_element_key = object_type_element.get("key")
                                for _key, _value in body.get("form_values").items():
                                    if _key == object_type_element_key and _value.get("choice_values") and len(_value.get("choice_values")) > 0 and _value.get("choice_values")[0]:
                                        object_type_id = _value.get("choice_values")[0]
                                        break
                        
                        if not object_type_id: # If Still Object Type not found (did not came from webhook) Ignore the image.
                            continue

                        for key, value in body.get("form_values").items(): # Loop through all input form_values
                            if key == element_key and len(value) > 0 and value[0].get("photo_id"): # If forms key matched webhooks values key then it is THE image
                                photo_id = value[0].get("photo_id")
                                # print(photo_id)
                                # Generate Public Image from this photo_id
                                url = 'https://api.fulcrumapp.com/api/v2/photos/'+photo_id+'.json'
                                headers = {
                                    "Accept": "application/json",
                                    "X-ApiToken": token
                                }
                                img_res = requests.request("GET", url, headers=headers)
                                if img_res.status_code == 200 or img_res.status_code == "200" or img_res.status_code == 201 or img_res.status_code == "201":
                                    img_meta = img_res.json()
                                    # print(img_meta)
                                    # TODO: Later Update app to receive "image_urls" as array of multiple image url in ISAC-SIMO API. Then combine all in same image model (same row).
                                    if img_meta and img_meta.get('photo') and img_meta.get('photo').get('original'):
                                        # We GOT the uploaded image Public Signed S3 URL successfully
                                        image_url = img_meta.get('photo').get('original')
                                        lat = body.get("latitude", None) # From webhook POST data
                                        lng = body.get("longitude", None) # From webhook POST data
                                        description = "Fulcrum / " + str(body.get("id", "N/A")) # From webhook POST data
                                        # Call ISAC-SIMO API with image url
                                        headers = {
                                            "Accept": "application/json"
                                        }
                                        if isac_token:
                                            headers["Authorization"] = "Bearer " + isac_token
                                        res = requests.post(isac_simo_api, data = {
                                            "description": description,
                                            "lat": lat,
                                            "lng": lng,
                                            "image_url": image_url,
                                            "object_type_id": object_type_id
                                        }, headers = headers)
                                        # print(res)
                                        # print(res.json())
                                        if res.status_code == 201 or res.status_code == "201" or res.status_code == 200 or res.status_code == "200":
                                            # SET FULCRUMS result field if it exists
                                            # AGAIN, LOOP through all elements to find the isac_result_xxx field and get its key.
                                            for result_element in elements:
                                                # print(result_field_start_with+isac_image_id)
                                                # print(result_element.get("data_name"))
                                                if result_element.get("data_name") == (result_field_start_with+isac_image_id):
                                                    element_key = result_element.get("key")

                                                    data = res.json()
                                                    if data.get("image_files") and len(data.get("image_files")) > 0:
                                                        result = data.get("image_files")[0].get("result", "")
                                                        score = data.get("image_files")[0].get("score", 0)
                                                        # print(result, score)
                                                        updated_form_values[element_key] = result # Assign key with isac-simo result (Note: updated_form_values is sent back to Fulcrum)
                                                    
                                            total_sent_to_isac_simo += 1;
        
        
        if total_sent_to_isac_simo > 0:
            # Combine Webhook form_values and updated_form_values
            uploading_form_values = body.get("form_values")
            uploading_form_values = {**uploading_form_values, **updated_form_values}
            # print(updated_form_values)
            # print(uploading_form_values)

            # CALL FULCRUM API TO UPDATE id submission data
            url = "https://api.fulcrumapp.com/api/v2/records/"+str(body.get("id",""))+".json"
            payload = {
                "record": {
                    "form_id": body.get("form_id"),
                    "latitude": body.get("latitude"),
                    "longitude": body.get("longitude"),
                    "form_values": uploading_form_values
                }
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-ApiToken": token
            }
            response = requests.request("PUT", url, json=payload, headers=headers)
            # print(response.text)
            return JsonResponse({"message":"OK"}, status=200)
        
    return JsonResponse({"message":"No Image Uploaded OR Object Type Id Provided OR Token is invalid"}, status=200)

# Contribution
class ContributionView(viewsets.ModelViewSet):
    queryset = Contribution.objects.all()
    serializer_class = ContributionSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["object_type_id"] = self.kwargs.get('object_id', 0) # GET object id from url route parameter and send to serializer
        return context

    def get_queryset(self):
        object_type_id = self.kwargs.get('object_id', 0) # GET object id from url route parameter
        if self.request.user.is_authenticated and object_type_id:
            query = self.request.GET.get('q','')
            own = self.request.GET.get('own', False) == 'true'
            helpful = self.request.GET.get('helpful', False) == 'true'

            if self.request.user.is_admin:
                contributions = Contribution.objects
            elif self.request.user.is_project_admin:
                projects = Projects.objects.filter(users__id=self.request.user.id).values_list('id', flat=True)
                contributions = Contribution.objects.filter(object_type__project_id__in=projects)
            else:
                if self.action == 'list':
                    contributions = Contribution.objects.filter(Q(is_helpful=True) | Q(created_by=self.request.user))
                else:
                    contributions = Contribution.objects.filter(created_by=self.request.user)
            
            if own:
                contributions = contributions.filter(created_by=self.request.user)
            if helpful:
                contributions = contributions.filter(is_helpful=True)
            if query:
                contributions = contributions.filter(Q(title__icontains=query) |
                                        Q(description__icontains=query) | Q(created_by__full_name__icontains=query))
            
            contributions = contributions.filter(object_type_id=object_type_id).order_by('-created_at').distinct().all();
            return contributions
        
        return []

    def destroy(self, request, *args, **kwargs):
        contribution = self.get_object()
        if contribution.file:
            contribution.file.delete()
        return super().destroy(request, *args, **kwargs)

