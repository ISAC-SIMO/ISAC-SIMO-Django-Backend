from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import user_passes_test
from importlib import reload

from main.authorization import *
from main.models import User

from .forms import ProjectForm
from .models import Projects
import isac_simo.classifier_list as classifier_list
from api.helpers import quick_test_detect_image
import json
import os

def reload_classifier_list():
    try:
        reload(classifier_list)
    except Exception as e:
        print('--------- [ERROR] FAILED TO RELOAD CLASSIFIER LIST MODULE [ERROR:OOPS] --------')

# View All Projects
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def viewProjects(request):
    if request.user.user_type == 'project_admin':
        projects = Projects.objects.filter(users__id=request.user.id).order_by('project_name')
    else:
        projects = Projects.objects.all().order_by('project_name')
    detect_model = classifier_list.detect_object_model_id + ' (Default)'
    return render(request, 'projects.html',{'projects':projects, 'detect_model':detect_model})

# Add Project
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def addProject(request, id = 0):
    if request.method == "GET":
        form = ProjectForm()
        return render(request,"add_project.html",{'form':form})
    elif request.method == "POST":
        form = ProjectForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            user = User.objects.get(id=request.user.id)
            instance = form.save(commit=False)
            instance.user = user
            instance.save()
            if request.user.user_type == 'project_admin':
                user.projects.add(instance)
            reload_classifier_list()
            messages.success(request, "New Project Added Successfully! (Make sure you add Object Types and Classifiers too)")
        else:
            messages.error(request, "Invalid Request")
            return render(request,"add_project.html",{'form':form})
        # if request.FILES.get('image'):
        #     myFile = request.FILES.get('image')
        #     fs = FileSystemStorage(location="main/media/project_images")
        #     filename = fs.save(myFile.name, myFile)
        #     projectform.image = 'project_images/'  + myFile.name    

    return redirect("viewprojects")

# Edit Projects
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def editProject(request, id=0):
    try:
        if request.user.user_type == 'project_admin':
            project = Projects.objects.filter(users__id=request.user.id).filter(id=id).prefetch_related('users').get()
        else:
            project = Projects.objects.filter(id=id).prefetch_related('users').get()
            
        if request.method == "GET":
            form = ProjectForm(instance=project)
            return render(request,"add_project.html",{'form':form, 'project':project})
        elif request.method == "POST":
            form = ProjectForm(request.POST or None, request.FILES or None, instance=project)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.save()
                reload_classifier_list()
                messages.success(request, "Project Updated Successfully!")
            else:
                messages.error(request, "Invalid Request")
                return render(request,"add_project.html",{'form':form, 'project':project})

        return redirect("viewprojects")
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project attempted to Edit")
        return redirect("viewprojects")

# Delete Project
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def deleteProject(request, id):
    try:
        if request.method == "POST":
            if request.user.user_type == 'project_admin':
                project = Projects.objects.filter(users__id=request.user.id).get(id=id)
            else:
                project = Projects.objects.get(id=id)
            project.image.delete()
            project.delete()
            reload_classifier_list()
            messages.success(request, 'Project Deleted Successfully!')
            return redirect('viewprojects')
        else:
            messages.error(request, 'Failed to Delete!')
            return redirect('viewprojects')
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project attempted to Delete")
        return redirect("viewprojects")

# Test Offline Detect Project
@user_passes_test(is_admin_or_project_admin, login_url=login_url)
def testOfflineProject(request, id):
    try:
        if request.user.user_type == 'project_admin':
            project = Projects.objects.filter(users__id=request.user.id).get(id=id)
        else:
            project = Projects.objects.get(id=id)
        if request.method == "GET":
            test_result = request.session.pop('test_result', False)
            return render(request, 'test.html', {"project": project, "test_result": test_result})
        elif request.method == "POST":
            try:
                if os.environ.get('PROJECT_FOLDER',False):
                    project_folder = os.environ.get('PROJECT_FOLDER','') + '/'
                else:
                    project_folder = ''

                # IF THIS PROJECT HAS OFFLINE MODEL THEN
                if project.offline_model:
                    quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.offline_model, offline=True, project_folder=project_folder)
                # ELSE ONLINE MODEL THEN
                else:
                    quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.detect_model, offline=False, project_folder=project_folder)
                
                if quick_test_image_result and len(quick_test_image_result) > 0:
                    request.session['test_result'] = json.dumps(quick_test_image_result, indent=4)
                    messages.success(request, 'Project Detect Model Test Success.')
                    messages.success(request, 'Score: '+str(quick_test_image_result[0]['pipeline']['score'])+' | Class: '+str(quick_test_image_result[0]['pipeline']['result']))
                else:
                    messages.error(request, 'Test Failed. Either No Object Was Detected or the model is not in ready state.')

                return redirect('testofflineproject', id=id)
            except Exception as e:
                print(e)
                messages.error(request, 'Project Detect Model Failed')
                return redirect('testofflineproject', id=id)

        messages.error(request, 'Invalid Project Test Attempt.')
        return redirect('viewprojects')
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project attempted to Test")
        return redirect("viewprojects")