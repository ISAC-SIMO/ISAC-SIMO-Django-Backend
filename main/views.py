from main.customdecorators import check_honeypot_conditional
from crowdsource.helpers import upload_object
from crowdsource.models import Crowdsource
from datetime import timedelta
import os
import subprocess
from importlib import reload
from urllib import request

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.staticfiles.views import serve
from django.core.files.storage import FileSystemStorage
from django.db.models.query import prefetch_related_objects
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from rest_framework.generics import get_object_or_404
from django.db.models import Q, Prefetch

import isac_simo.classifier_list as classifier_list
from api.models import Image, ImageFile
from main.authorization import *
from projects.models import Projects

from .forms import (AdminEditForm, AdminRegisterForm, LoginForm, ProfileForm,
                    RegisterForm)
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken


def reload_classifier_list():
    try:
        reload(classifier_list)
    except Exception as e:
        print('--------- [ERROR] FAILED TO RELOAD CLASSIFIER LIST MODULE [ERROR:OOPS] --------')

# HOME PAGE INDEX FOR NORMAL USER
def index(request):
    return render(request, 'index.html')

@login_required
def home(request):
    # reload_classifier_list()
    if(is_admin(request.user)):
        images = Image.objects.order_by('-created_at').all().prefetch_related('image_files')
        image_files_count = ImageFile.objects.filter(tested=True).count()
        user_count = User.objects.all().count()
        project_count = Projects.objects.all().count()
    elif(is_government(request.user)):
        projects = Projects.objects.filter(users__id=request.user.id)
        images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).order_by('-created_at').prefetch_related('image_files').distinct()
        image_files_count = 0
        for image in images:
            image_files_count = image_files_count + image.image_files.all().count()
        user_count = 0
        project_count = 0
    elif(is_project_admin(request.user)):
        projects = Projects.objects.filter(users__id=request.user.id)
        images = Image.objects.filter(Q(user_id=request.user.id) | Q(project__in=projects)).order_by('-created_at').prefetch_related('image_files').distinct()
        image_files_count = 0
        for image in images:
            image_files_count = image_files_count + image.image_files.all().count()
        user_count = User.objects.filter(Q(projects__in=projects)).count()
        project_count = len(projects)
    else:
        images = Image.objects.filter(user_id=request.user.id).order_by('-created_at').prefetch_related('image_files')
        image_files_count = 0
        for image in images:
            image_files_count = image_files_count + image.image_files.all().count()
        user_count = 0
        project_count = 0

    focus_at = ''
    if request.GET.get('focus_at', False):
        focus_at = request.GET.get('focus_at')
    return render(request, 'dashboard.html', {'focus_at':focus_at,'images':images,'user_count':user_count,'image_files_count':image_files_count,'project_count':project_count})

@login_required
def profile(request):
    if request.method == "GET":
        edituser = User.objects.get(id=request.user.id)
        profileform = ProfileForm(instance=edituser)
        return render(request, 'auth/profile.html', {'user': request.user, 'form': profileform})
    elif request.method == "POST":
        updateUser = User.objects.get(id=request.user.id)
        updateUser.email = request.POST.get('email')
        updateUser.full_name = request.POST.get('full_name')

        password1 = request.POST.get('password1') 
        password2 = request.POST.get('password2')

        if request.FILES.get('image'):
            if(updateUser.image != 'user_images/default.png'):
                updateUser.image.delete()
            myFile = request.FILES.get('image')
            updateUser.image = myFile
            # fs = FileSystemStorage(location="mainApp/media/user_images")
            # filename = fs.save(myFile.name, myFile)
            # updateUser.image = 'user_images/'  + myFile.name
        if password1 and password2:
            if password1 != password2:
                messages.error(request, "Password Mismatch")
                return redirect(request.META['HTTP_REFERER'])
            else:
                updateUser.set_password(password1)
        else:
            if password1 or password2:
                messages.error(request, "Fill up password in both the fields")
                return redirect(request.META['HTTP_REFERER'])

        updateUser.save()
        messages.success(request,"User Info Updated Successfully!")
        return redirect("dashboard")

@user_passes_test(is_admin_or_project_admin, login_url=dashboard_url)
def generate_token(request):
    if request.method == "POST":
        refresh = RefreshToken.for_user(request.user)
        access_token = refresh.access_token
        access_token.set_exp(lifetime=timedelta(days=365*111)) # Remind me in 111 years
        access_token["external"] = True
        return JsonResponse({'token': str(access_token)}, status=200)
    
    return JsonResponse({'message':'Invalid Request Sent'}, status=404)

@check_honeypot_conditional
@user_passes_test(is_guest, login_url=dashboard_url)
def login_user(request):
    if request.method == "POST":
        # reload_classifier_list()
        user = authenticate(username = request.POST.get('email'), password = request.POST.get('password'))
        if user is not None:
            # If user disabled i.e. active = False
            if not user.active:
                messages.error(request, 'User Account has been Disabled. Please contact Admin.')
                form = LoginForm(request.POST)
                return render(request, 'auth/login.html', {'form':form})

            if request.POST.get('remember') is not None:    
                request.session.set_expiry(1209600)
            login(request, user)
            # CHECK AND LINK CROWDSOURCE CONTRIBUTION TO THIS ACCOUNT
            crowdsource_images = request.session.get('crowdsource_images', [])
            crowdsource_images_linked = 0
            for img in crowdsource_images:
                if img.get('id'):
                    crowdsource_image = Crowdsource.objects.filter(id=img.get('id')).get()
                    if crowdsource_image and not crowdsource_image.created_by_id:
                        crowdsource_image.created_by_id = user.id
                        crowdsource_image.username = user.full_name
                        crowdsource_image.save()
                        upload_object(crowdsource_image.bucket_key(), crowdsource_image.filepath())
                        crowdsource_images_linked += 1
            if crowdsource_images_linked and crowdsource_images_linked > 0:
                messages.info(request, str(crowdsource_images_linked) + ' Crowdsource Image has been linked to your account.')
            request.session.pop('crowdsource_images', None)

            if request.POST.get('next'): # Go Back to Previous route (e.g. in case was logged out)
                return HttpResponseRedirect(request.POST.get('next'))
            return redirect('dashboard')
        else:
            form = LoginForm(request.POST)
            messages.error(request, 'Invalid User Credentials')
            next = False
            if request.POST.get('next'):
                next = request.POST.get('next')
            return render(request, 'auth/login.html', {'form':form, 'next':next})
    else:
        if not request.user.is_authenticated:
            if request.GET.get('error') == 'unauthorized':
                messages.error(request, 'Unauthorized Access. Login to Continue.')
            next = False
            if request.GET.get('next'): # Store Next Route
                next = request.GET.get('next')
            form = LoginForm()
            return render(request, 'auth/login.html', {'form':form, 'next':next})
        else:
            storage = messages.get_messages(request)
            storage.used = True
            if request.GET.get('error') == 'unauthorized':
                messages.error(request, 'Unauthorized Access was denied.')
            return redirect('dashboard')

@check_honeypot_conditional
@user_passes_test(is_guest, login_url=dashboard_url)
def register(request):
    registerForm = RegisterForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if registerForm.is_valid():
            instance = registerForm.save(commit=False)
            instance.set_password(request.POST.get('password1'))
            if request.POST.get('type', False) and request.POST.get('type') == 'project_admin':
                instance.user_type = 'project_admin'
                instance.active = False
            instance.save()

            storage = messages.get_messages(request)
            storage.used = True
            if request.POST.get('type', False) and request.POST.get('type') == 'project_admin':
                messages.info(request, 'You have been registered as Project Admin. But, you cannot login immediently. Please contact Admin to enable your account. Thank You.')
            else:
                messages.success(request, 'Registration Success. Login Now.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid Form Request')
    
    if not request.user.is_authenticated:
        return render(request, "auth/register.html", {"form": registerForm})
    else:
        return redirect('dashboard')

@login_required
def logout_user(request):
    logout(request)
    messages.success(request, 'Logged Out Successfully')
    return redirect('login')

@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def list_all_users(request):
    if request.user.is_project_admin:
        users = User.objects.exclude(user_type='admin').order_by('-timestamp', '-active').prefetch_related(
            Prefetch(
                "projects",
                queryset=Projects.objects.filter(users__id=request.user.id).distinct(),
                to_attr="visible_projects"
            )
        )
    else:
        users = User.objects.all().order_by('-timestamp', '-active').prefetch_related(
            Prefetch(
                "projects",
                queryset=Projects.objects.all(),
                to_attr="visible_projects"
            )
        )
    return render(request, 'users/allusers.html',{'users':users})

# Add Users via Admin Panel Dashboard
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def admin_userAddForm(request, id=0):
    if request.method == "GET":
        if id == 0:
            adminRegisterForm = AdminRegisterForm(request=request)
        else:
            edituser = User.objects.get(id=id)
            if edituser.is_admin and not request.user.is_admin:
                messages.error(request, 'Cannot Update Higher Authorized User')
                return redirect('allusers')

            adminRegisterForm = AdminEditForm(instance=edituser,request=request)
        return render(request, "users/admin_register.html", {"form": adminRegisterForm})
    elif request.method == "POST":
        if id == 0:
            form = AdminRegisterForm(request.POST or None, request.FILES or None, request=request)

            if form.is_valid():
                instance = form.save(commit=False)
                instance.save()
                form.save_m2m()
                messages.success(request, "User Added Successfully!")
            else:
                return render(request, "users/admin_register.html", {"form": form})
        else:
            updateUser = User.objects.get(id=id)
            if updateUser.is_admin and not request.user.is_admin:
                messages.error(request, 'Cannot Update Higher Authorized User')
                return redirect('allusers')

            updateUser.email = request.POST.get('email')
            updateUser.full_name = request.POST.get('full_name')
            updateUser.user_type = request.POST.get('user_type')
            if request and request.user.is_project_admin:
                updateUser.projects.add(*Projects.objects.filter(users__id=request.user.id).filter(id__in=request.POST.getlist('projects')))
            else:
                updateUser.projects.set(Projects.objects.filter(id__in=request.POST.getlist('projects')))

            password1 = request.POST.get('password1') 
            password2 = request.POST.get('password2')

            if request.FILES.get('image'):
                if(updateUser.image != 'user_images/default.png'):
                    updateUser.image.delete()
                myFile = request.FILES.get('image')
                updateUser.image = myFile
                # fs = FileSystemStorage(location="mainApp/media/user_images")
                # filename = fs.save(myFile.name, myFile)
                # updateUser.image = 'user_images/'  + myFile.name
            if password1 and password2:
                if password1 != password2:
                    messages.info(request, "Password Mismatch")
                    return redirect(request.META['HTTP_REFERER'])
                else:
                    updateUser.set_password(password1)
            else:
                if password1 or password2:
                    messages.info(request, "Fill up password in both the fields")
                    return redirect(request.META['HTTP_REFERER'])

            if request.POST.get('active', False):
                updateUser.active = True
            else:
                updateUser.active = False
            updateUser.save()
            messages.info(request,"User Record Updated Successfully for "+updateUser.full_name+"!")

        return redirect("allusers")

# Add Users via Admin Panel Dashboard
@user_passes_test(is_admin, login_url=login_url)
def deleteUserByAdmin(request, id):
    if request.method == "POST":
        user = User.objects.get(id=id)
        if(user.image != 'user_images/default.png'):
            user.image.delete()
        user.delete()
        messages.success(request, 'User Record Deleted Successfully!')
        return redirect('allusers')
    else:
        messages.error(request, 'Failed to Delete!')
        return redirect('allusers')

# Pull From Git Master via Route
def pull(request):
    if os.getenv('PASSWORD', False) and os.getenv('PASSWORD', False) == request.GET.get('password', ''):
        name = os.environ.get('PROJECT_FOLDER','') + '/pull.sh'
        print('pull.sh exists: '+ str(os.path.exists(name)))
        path = os.path.join(name)

        if not os.path.exists(name):
            path = './pull.sh'

        print(path)

        subprocess.call(path, shell=True)
        return JsonResponse({'status':'ok'}, status=200)

    print('--~~ PULL FAILED ~~--')
    return JsonResponse({'status':'bad'}, status=404)

# Service Worker js response
def serviceworker(request):
    try:
        saveto = os.path.join('static/js/serviceworker.js')
        if not os.path.exists(saveto):
            saveto = os.environ.get('PROJECT_FOLDER','') + '/static/js/serviceworker.js'

        return HttpResponse(open(saveto), 'application/javascript')
    except Exception as e:
        print(e)
        return render(request, '404.html', status=404)

def offline(request):
    return render(request, 'offline.html')