from django.http.response import HttpResponseRedirect
from api.models import ObjectType
from django.core.cache import cache
from crowdsource.helpers import delete_object, get_object, get_object_list, move_object, upload_object
from crowdsource.forms import CrowdsourceForm
from crowdsource.models import Crowdsource
from django.shortcuts import get_object_or_404, redirect, render
from main.authorization import login_url, is_admin_or_project_admin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import serializers
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from .serializers import CrowdsourceSerializer
from rest_framework.response import Response
import uuid
import json

# View All Crowdsource Images + Update/Create

def crowdsource_images(request):
    dash = request.user and not request.user.is_anonymous
    if dash:
        dash = "master/base.html"
    else:
        dash = "master/blank.html"

    if request.method == "GET":
        crowdsource_images = []
        query = request.GET.get('q','')
        if request.user and not request.user.is_anonymous:
            if(is_admin_or_project_admin(request.user)):
                crowdsource_images = Crowdsource.objects.order_by(
                    '-created_at').filter(Q(object_type__icontains=query) |
                                        Q(image_type__icontains=query) |
                                        Q(username__icontains=query)).distinct().all()
            else:
                crowdsource_images = Crowdsource.objects.filter(
                    created_by=request.user).order_by('-created_at').filter(Q(object_type__icontains=query) |
                                        Q(image_type__icontains=query) |
                                        Q(username__icontains=query)).distinct().all()

            paginator = Paginator(crowdsource_images, 50)  # Show 50
            page_number = request.GET.get('page', '1')
            crowdsources = paginator.get_page(page_number)
        else:
            crowdsources = False

        form = CrowdsourceForm()

        return render(request, 'crowdsource_images.html', {'crowdsources': crowdsources, 'form': form, 'query': query, 'dash': dash})
    elif request.method == "POST":
        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # EDIT
            try:
                if(is_admin_or_project_admin(request.user)):
                    crowdsource_image = Crowdsource.objects.filter(
                        id=request.POST.get('id')).get()
                elif request.user.is_authenticated:
                    crowdsource_image = Crowdsource.objects.filter(
                        created_by=request.user).filter(id=request.POST.get('id')).get()
                else:
                    crowdsource_images = request.session.get('crowdsource_images', [])
                    crowdsource_image = False
                    for img in crowdsource_images:
                        if str(img.get('id')) == request.POST.get('id'):
                            crowdsource_image = Crowdsource.objects.filter(id=request.POST.get('id')).get()
                    if not crowdsource_image:
                        messages.error(request, "Invalid Crowdsource Image attempted to edit.")
                        return redirect("crowdsource")

                form = CrowdsourceForm(
                    request.POST or None, instance=crowdsource_image)
                old_object_key = crowdsource_image.bucket_key()
                crowdsource_images = request.session.get('crowdsource_images', [])
                if form.is_valid():
                    instance = form.save(commit=False)
                    if not instance.username:
                        if not request.user.is_authenticated:
                            instance.username = "Anonymous User - " + uuid.uuid4().hex[:6].upper()
                    instance.save()

                    for idx, val in enumerate(crowdsource_images):
                        if str(val.get("id")) == str(instance.id):
                            crowdsource_images[idx] = {'id': instance.id, 'file': instance.file.url, 'object_type': instance.object_type, 'image_type': instance.image_type, 'username': instance.username}
                    request.session['crowdsource_images'] = crowdsource_images
                    
                    if request.user.is_authenticated and old_object_key != instance.bucket_key():
                        move_object(instance.bucket_key(), old_object_key)
                    messages.success(
                        request, "Crowdsource Image Updated Successfully")
                    return redirect("crowdsource")
            except(Crowdsource.DoesNotExist):
                pass
        else:
            # TODO: FOR NOW LIMIT 5 TOTAL UPLOADS BY SAME USER ( SAME BELOW )
            if request.user.is_authenticated:
                if(Crowdsource.objects.filter(created_by=request.user).count() >= 5):
                    messages.error(request, "Currently you can only upload 5 images. More will be enabled later.")
                    return redirect("crowdsource")
            else:
                if(len(request.session.get('crowdsource_images', [])) >= 5):
                    messages.error(request, "Currently you can only upload 5 images. More will be enabled later.")
                    return redirect("crowdsource")

            # Create
            total = 0
            crowdsource_images = request.session.get('crowdsource_images', [])
            for _file in request.FILES.getlist('file'):
                request.FILES['file'] = _file
                form = CrowdsourceForm(
                    request.POST or None, request.FILES or None)
                if form.is_valid():
                    instance = form.save(commit=False)
                    if request.user.is_authenticated:
                        instance.created_by = request.user
                    else:
                        instance.username = "Anonymous User - " + uuid.uuid4().hex[:6].upper()
                    instance.save()
                    crowdsource_images.append({'id': instance.id, 'file': instance.file.url, 'object_type': instance.object_type, 'image_type': instance.image_type, 'username': instance.username})
                    request.session['crowdsource_images'] = crowdsource_images

                    if request.user.is_authenticated and settings.PRODUCTION:
                        upload_object(instance.bucket_key(), instance.filepath())
                    total += 1
                    if total >= 5:
                        break; # TODO: FOR NOW LIMIT 5 TOTAL UPLOADS BY SAME USER

            messages.success(request, "Yay, " +str(total)+ " New Image(s) Contributed to Crowdsource.")
            return redirect("crowdsource")

    messages.error(request, "Invalid Request")
    return redirect("crowdsource")


@login_required(login_url=login_url)
def crowdsource_images_delete(request, id):
    if request.method == "POST":
        try:
            if request.user.is_admin or request.user.is_project_admin:
                crowdsource_image = Crowdsource.objects.filter(id=id).get()
            else:
                crowdsource_image = Crowdsource.objects.filter(created_by=request.user).filter(id=id).get()
            
            if crowdsource_image:
                delete_object(crowdsource_image.bucket_key())
                crowdsource_image.file.delete()
                crowdsource_image.delete()
                messages.success(
                    request, 'Crowdsource Image Deleted Successfully!')
                return redirect("crowdsource")
        except(Crowdsource.DoesNotExist):
            pass

    messages.error(request, "Invalid Request")
    return redirect("crowdsource")

@login_required(login_url=login_url)
def image_request_download(request, id):
    # TODO: if ImageRequest / ImageShare Model status is accepted. and created_at is not too much PAST (> 30 days)
    # Allow user to download the file of object type they had chosen to
    images = get_object_list('wall') # Of the object type
    if images:
        dump = json.dumps(images)
        response = HttpResponse(dump, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=wall.json' # file name as object type
        return response
    else:
        messages.error(request, "Unable to Download Image List at the moment.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))

#######
# API #
#######

class ResponseInfo(object):
    def __init__(self, user=None, **args):
        self.response = {
            "data": args.get('data', []),
            "page": args.get('message', '1'),
            "object_types": args.get('object_types',[])
        }

# Crowdsource Image API
class CrowdsourceView(viewsets.ModelViewSet):
    queryset = Crowdsource.objects.all()
    serializer_class = CrowdsourceSerializer
    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(CrowdsourceView, self).__init__(**kwargs)

    def get_queryset(self):
        if self.action == 'list':
            page = abs(int(self.request.GET.get('page', 1)))
            offset = 100 * (page - 1)
            limit = 100
            offsetPlusLimit = offset + limit
            query = self.request.GET.get('q','')
            if self.request.user.is_authenticated:
                # ALL FOR ADMIN / PA
                if self.request.user.is_admin or self.request.user.is_project_admin:
                    ids = Crowdsource.objects.order_by('-created_at').filter(Q(object_type__icontains=query) |
                                                                            Q(image_type__icontains=query) |
                                                                            Q(username__icontains=query)).values_list('pk', flat=True)[offset:offsetPlusLimit] # Latest 100
                    return Crowdsource.objects.filter(pk__in=list(ids)).order_by('-created_at')
                # OWN FOR OTHER
                else:
                    ids = Crowdsource.objects.order_by('-created_at').filter(created_by=self.request.user).filter(Q(object_type__icontains=query) |
                                                                            Q(image_type__icontains=query) |
                                                                            Q(username__icontains=query)).values_list('pk', flat=True)[offset:offsetPlusLimit] # Latest 100
                    return Crowdsource.objects.filter(pk__in=list(ids)).order_by('-created_at')
            else:
                return []
        else:
            if self.request.user.is_authenticated:
                # ALL FOR ADMIN / PA
                if self.request.user.is_admin or self.request.user.is_project_admin:
                    return Crowdsource.objects.order_by('-created_at')
                # OWN FOR OTHER
                else:
                    return Crowdsource.objects.filter(created_by=self.request.user).order_by('-created_at')
            else:
                return []

    def list(self, request, *args, **kwargs):
        response_data = super(CrowdsourceView, self).list(request, *args, **kwargs)
        self.response_format["data"] = response_data.data

        page = str(abs(int(self.request.GET.get('page', 1))))
        self.response_format["page"] = page
        
        OBJECT_TYPE = cache.get('all_object_type_choices_json',[])
        if not OBJECT_TYPE:
          OBJECT_TYPE = [
            {"value":"other", "title":"Other"}
          ]

          all_object_types = ObjectType.objects.order_by('name').values_list('name', flat=True).distinct()
          for o in all_object_types:
            OBJECT_TYPE.append({"value":o, "title":o.title()})
          cache.set('all_object_type_choices_json', OBJECT_TYPE)
        self.response_format["object_types"] = OBJECT_TYPE
        
        return Response(self.response_format)

    def destroy(self, request, *args, **kwargs):
        crowdsource_image = self.get_object()
        delete_object(crowdsource_image.bucket_key())
        crowdsource_image.file.delete()
        return super().destroy(request, *args, **kwargs)
