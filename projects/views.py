from api.models import Contribution, ObjectType
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.http.response import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required, user_passes_test
from importlib import reload

from main.authorization import *
from main.models import User

from .forms import ProjectForm
from .models import Projects
import isac_simo.classifier_list as classifier_list
from api.helpers import quick_test_detect_image
import json
import os
from django.db.models import Q

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
        if Projects.objects.filter(guest=True).count() > 1:
            messages.info(request, "INFO: More then 1 Global Projects Found. Having only one Global/Guest Project is best approach.", extra_tags="info tiny")

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

            # IF GUEST type is checked
            if request.POST.get('guest', False):
                instance.guest = True

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
            was_public = project.public
            form = ProjectForm(request.POST or None, request.FILES or None, instance=project)
            if form.is_valid():
                instance = form.save(commit=False)

                # IF GUEST type is checked
                if request.POST.get('guest', False):
                    instance.guest = True
                else:
                    instance.guest = False

                if was_public and not instance.public and request.POST.get('unpublic', False):
                    # Remove all linked users except self.
                    for u in project.users.all():
                        if u.id != request.user.id:
                            project.users.remove(u)

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
                    quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.offline_model, offline=True, project_folder=project_folder, ibm_api_key=project.ibm_api_key)
                # ELSE ONLINE MODEL THEN
                else:
                    quick_test_image_result = quick_test_detect_image(request.FILES.get('file', False), project.detect_model, offline=False, project_folder=project_folder, ibm_api_key=project.ibm_api_key)
                
                if quick_test_image_result:
                    if isinstance(quick_test_image_result, dict) and quick_test_image_result.get("error", False):
                        request.session['test_result'] = json.dumps(quick_test_image_result, indent=4)
                        messages.error(request, 'Nothing was Detected.')
                    elif len(quick_test_image_result) > 0:
                        request.session['test_result'] = json.dumps(quick_test_image_result, indent=4)
                        messages.success(request, 'Project Detect Model Test Success.')
                        messages.success(request, 'Score: '+str(quick_test_image_result[0]['pipeline']['score'])+' | Class: '+str(quick_test_image_result[0]['pipeline']['result']))
                    else:
                        request.session['test_result'] = quick_test_image_result
                        messages.error(request, 'Test Success, but Bad Response type')
                else:
                    print(quick_test_image_result)
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

# View All Publicly Shared public=true Projects
@user_passes_test(login_required, login_url=login_url)
def publicProjects(request):
    projects_list = []
    query = request.GET.get('q','')
    joined = request.GET.get('joined',False)

    projects_list = Projects.objects.order_by('-updated_at')

    # FILTER AND SHOW ONLY JOINED
    if joined == 'true':
        projects_list = projects_list.filter(Q(users__id=request.user.id))
    # ELSE ALL
    else:
        projects_list = projects_list.filter(Q(public=True) | Q(users__id=request.user.id))

    # IF SEARCH
    if query and len(query) > 0:
        projects_list = projects_list.filter(Q(project_name__icontains=query) |
                                            Q(project_desc__icontains=query) |
                                            Q(object_types__name__icontains=query))
    
    projects_list = projects_list.distinct().all()

    paginator = Paginator(projects_list, 25)  # Show 25
    page_number = request.GET.get('page', '1')
    projects = paginator.get_page(page_number)

    joined_projects = request.user.projects.all().values_list('id', flat=True);
    return render(request, 'public_projects.html',{'projects':projects,'joined_projects':joined_projects,'query':query,'joined':joined})

# Join or Leave a Public Project
@user_passes_test(login_required, login_url=login_url)
def publicProjectJoin(request, id):
    try:
        if request.method == "POST":
            join = request.GET.get('join', False) # join=True or Leave
            if join: # JOIN
                project = Projects.objects.filter(public=True).get(id=id)
                request.user.projects.add(project)
            else: # LEAVE
                project = Projects.objects.get(id=id)
                request.user.projects.remove(project)
                if not project.public:
                    messages.warning(request, 'Note: The Project you left was Not Public Project. Thus, cannot be joined by yourself.')

            messages.success(request, ('Project Joined Successfully.' if join else 'Project Left Successfully'))
        else:
            messages.error(request, 'Something went wrong. Invalid Request.')
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project")
    
    if request.META.get('HTTP_REFERER', False):
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        return redirect('public_projects')

# Public Project Info Page with Object Types and Classifiers details
@user_passes_test(login_required, login_url=login_url)
def publicProjectInfo(request, id):
    try:
        project = Projects.objects.filter(Q(public=True) | Q(users__id=request.user.id)).distinct().prefetch_related('object_types', 'object_types__classifiers','object_types__classifiers__offline_model').get(id=id)
        joined = True if request.user.projects.filter(id=project.id).count() > 0 else False
        return render(request, 'public_project_info.html',{'project':project, 'joined':joined})
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project. The Project does not exist.")
        return redirect('public_projects')

# Add Contribution
@user_passes_test(login_required, login_url=login_url)
def addContribution(request, id, object_id):
    try:
        project = Projects.objects.filter(Q(public=True) | Q(users__id=request.user.id)).distinct().get(id=id)
        joined = True if request.user.projects.filter(id=project.id).count() > 0 else False
        object_type = ObjectType.objects.filter(project_id=project.id).get(id=object_id)

        # List Contributions
        if request.method == "GET":
            contributions = []
            query = request.GET.get('q','')
            own = request.GET.get('own', False) == 'true'

            if(request.user.is_admin or request.user.is_project_admin):
                contributions = Contribution.objects
            else:
                contributions = Contribution.objects.filter(Q(is_helpful=True) | Q(created_by=request.user))
            
            if own:
                contributions = contributions.filter(created_by=request.user)
            if query:
                contributions = contributions.filter(Q(title__icontains=query) |
                                        Q(description__icontains=query))
            
            contributions = contributions.order_by('-created_at').distinct().all();

            paginator = Paginator(contributions, 50)  # Show 50
            page_number = request.GET.get('page', '1')
            contributions = paginator.get_page(page_number)
            return render(request, 'contribution_list.html',{'contributions':contributions, 'query':query, 'own':own, 'project': project, 'object_type':object_type,'joined':joined})
        # Add Contributions
        elif request.method == "POST":
            if joined:
                if object_type.wishlist:
                    contribution = Contribution.objects.create(
                        title=request.POST.get('title', None),
                        description=request.POST.get('description', None),
                        file=request.FILES.get('file', None),
                        object_type=object_type,
                        created_by=request.user
                    )
                    messages.success(request, "Contribution Submitted Successfully for Project: "+project.project_name+" & Object Type: "+object_type.name)
                else:
                    messages.error(request, "Contribution has not been enabled for this Object Type.")
            else:
                messages.error(request, "You have not Joined the Project. Please, Join to Contribute.")
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Project. The Project does not exist or is not available at the moment.")
    except(Projects.DoesNotExist):
        messages.error(request, "Invalid Object Type. The Object type you trying to access does not exist.")

    if request.META.get('HTTP_REFERER', False):
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        return redirect('public_projects')