from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http.response import HttpResponseRedirect
from api.models import ObjectType
from django.core.cache import cache
from crowdsource.forms import CrowdsourceForm, ImageShareForm
from crowdsource.helpers import delete_object, get_object, get_object_list, move_object, upload_object
from crowdsource.models import Crowdsource, ImageShare
from django.shortcuts import get_object_or_404, redirect, render
from main.authorization import login_url, is_admin_or_project_admin, is_admin
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
from django.utils import timezone
from datetime import timedelta


# View All Crowdsource Images + Update/Create

def crowdsource_images(request):
    dash = request.user and not request.user.is_anonymous
    if dash:
        dash = "master/base.html"
    else:
        dash = "master/blank.html"

    if request.method == "GET":
        crowdsource_images = []
        query = request.GET.get('q', '')
        if request.user and not request.user.is_anonymous:
            if (is_admin(request.user)):
                crowdsource_images = Crowdsource.objects.order_by(
                    '-created_at').filter(Q(object_type__icontains=query) |
                                          Q(image_type__icontains=query) |
                                          Q(username__icontains=query)).distinct().all()
            else:
                crowdsource_images = Crowdsource.objects.filter(
                    created_by=request.user).order_by('-created_at').filter(Q(object_type__icontains=query) |
                                                                            Q(image_type__icontains=query) |
                                                                            Q(
                                                                                username__icontains=query)).distinct().all()

            paginator = Paginator(crowdsource_images, 50)  # Show 50
            page_number = request.GET.get('page', '1')
            crowdsources = paginator.get_page(page_number)
        else:
            crowdsources = False

        form = CrowdsourceForm(request=request)

        return render(request, 'crowdsource_images.html',
                      {'crowdsources': crowdsources, 'form': form, 'query': query, 'dash': dash})
    elif request.method == "POST":
        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # EDIT
            try:
                if (is_admin(request.user)):
                    crowdsource_image = Crowdsource.objects.filter(
                        id=request.POST.get('id')).get()
                elif request.user.is_authenticated:
                    crowdsource_image = Crowdsource.objects.filter(
                        created_by=request.user).filter(id=request.POST.get('id')).get()
                else:
                    # Check if Session has that image
                    crowdsource_images = request.session.get('crowdsource_images', [])
                    crowdsource_image = False
                    for img in crowdsource_images:
                        if str(img.get('id')) == request.POST.get('id'):
                            crowdsource_image = Crowdsource.objects.filter(id=request.POST.get('id')).get()
                    if not crowdsource_image:
                        messages.error(request, "Invalid Crowdsource Image attempted to edit.")
                        return redirect("crowdsource")

                form = CrowdsourceForm(
                    request.POST or None, instance=crowdsource_image, request=request)
                old_object_key = crowdsource_image.bucket_key()
                crowdsource_images = request.session.get('crowdsource_images', [])
                if form.is_valid():
                    instance = form.save(commit=False)
                    if not instance.username:
                        if not request.user.is_authenticated:
                            instance.username = "Anonymous User - " + uuid.uuid4().hex[:6].upper()
                    instance.save()

                    # Updating the Session
                    for idx, val in enumerate(crowdsource_images):
                        if str(val.get("id")) == str(instance.id):
                            crowdsource_images[idx] = {'id': instance.id, 'file': instance.file.url,
                                                       'object_type': instance.object_type,
                                                       'image_type': instance.image_type, 'username': instance.username}
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
            if request.user.is_authenticated and not is_admin(request.user):
                if (Crowdsource.objects.filter(created_by=request.user).count() >= 5):
                    messages.error(request, "Currently you can only upload 5 images. More will be enabled later.")
                    return redirect("crowdsource")
            elif not request.user.is_authenticated:
                if (len(request.session.get('crowdsource_images', [])) >= 5):
                    messages.error(request, "Currently you can only upload 5 images. More will be enabled later.")
                    return redirect("crowdsource")

            # Create
            total = 0
            crowdsource_images = request.session.get('crowdsource_images', [])
            for _file in request.FILES.getlist('file'):
                request.FILES['file'] = _file

                # If direct_upload is chosen by Admin. Upload directly to IBM BUCKET
                if request.POST.get('direct_upload') and is_admin(request.user):
                    if type(_file) is InMemoryUploadedFile:
                        image_file_path = _file.open()
                    else:
                        image_file_path = open(_file.temporary_file_path(), 'rb')

                    ext = image_file_path.__str__().split('.')[-1]
                    filename = '{}.{}'.format(uuid.uuid4().hex, ext)
                    key = request.POST.get('object_type', 'error') + '/' + filename
                    upload_object(key, image_file_path, opened=True)
                    total += 1
                    print(key + " Uploaded as DIRECT-UPLOAD to IBM COS Bucket")
                else:
                    form = CrowdsourceForm(
                        request.POST or None, request.FILES or None, request=request)
                    if form.is_valid():
                        instance = form.save(commit=False)
                        if request.user.is_authenticated:
                            instance.created_by = request.user
                        else:
                            instance.username = "Anonymous User - " + uuid.uuid4().hex[:6].upper()
                        instance.save()
                        crowdsource_images.append(
                            {'id': instance.id, 'file': instance.file.url, 'object_type': instance.object_type,
                             'image_type': instance.image_type, 'username': instance.username})
                        request.session['crowdsource_images'] = crowdsource_images

                        if request.user.is_authenticated and settings.PRODUCTION:
                            upload_object(instance.bucket_key(), instance.filepath())
                        total += 1

                if not request.user.is_authenticated or not is_admin(request.user):
                    if total >= 5:
                        break;  # TODO: FOR NOW LIMIT 5 TOTAL UPLOADS BY SAME USER

            messages.success(request, "Yay, " + str(total) + " New Image(s) Contributed to Crowdsource.")
            return redirect("crowdsource")

    messages.error(request, "Invalid Request")
    return redirect("crowdsource")


@login_required(login_url=login_url)
def crowdsource_images_delete(request, id):
    if request.method == "POST":
        try:
            if request.user.is_admin:
                crowdsource_image = Crowdsource.objects.filter(id=id).get()
            else:
                crowdsource_image = Crowdsource.objects.filter(created_by=request.user).filter(id=id).get()

            if crowdsource_image:
                if not request.user.is_admin:
                    delete_object(crowdsource_image.bucket_key())
                elif request.GET.get('bucket', '') != 'no':
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
def image_share_download(request, id):
    # Allow user to download the file of object type they had chosen to
    if request.method == "POST":
        if request.user.is_admin:
            image_share = ImageShare.objects.filter(id=id).get()
        else:
            image_share = ImageShare.objects.filter(user=request.user).filter(id=id).get()
        
        if image_share and image_share.object_type:
            if image_share.status == "accepted": # If request was accepted
                if ( (timezone.now() - image_share.created_at).days < 30 ): # If created_at is not older then 30 days. Allow to download.
                    images = get_object_list(image_share.object_type) # Download image of the chosen object type
                    if images:
                        dump = json.dumps(images)
                        response = HttpResponse(dump, content_type='application/json')
                        response['Content-Disposition'] = 'attachment; filename='+image_share.object_type+'.json' # file name as object type
                        return response
                    else:
                        messages.error(request, "Unable to Download Image List at the moment. Might be empty.")
                        return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))
                else:
                    messages.error(request, "Image Share Request has expired (older then 30 days). Please send another request.")
            else:
                messages.error(request, "Image Share Request has not been accepted.")
        else:
            messages.error(request, "Invalid Request")
    
    return redirect("images_share")

#######
# API #
#######

class ResponseInfo(object):
    def __init__(self, user=None, **args):
        self.response = {
            "data": args.get('data', []),
            "page": args.get('message', '1'),
            "object_types": args.get('object_types', [])
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
            query = self.request.GET.get('q', '')
            if self.request.user.is_authenticated:
                # ALL FOR ADMIN
                if self.request.user.is_admin:
                    ids = Crowdsource.objects.order_by('-created_at').filter(Q(object_type__icontains=query) |
                                                                             Q(image_type__icontains=query) |
                                                                             Q(username__icontains=query)).values_list(
                        'pk', flat=True)[offset:offsetPlusLimit]  # Latest 100
                    return Crowdsource.objects.filter(pk__in=list(ids)).order_by('-created_at')
                # OWN FOR OTHER
                else:
                    ids = Crowdsource.objects.order_by('-created_at').filter(created_by=self.request.user).filter(
                        Q(object_type__icontains=query) |
                        Q(image_type__icontains=query) |
                        Q(username__icontains=query)).values_list('pk', flat=True)[offset:offsetPlusLimit]  # Latest 100
                    return Crowdsource.objects.filter(pk__in=list(ids)).order_by('-created_at')
            else:
                return []
        else:
            if self.request.user.is_authenticated:
                # ALL FOR ADMIN
                if self.request.user.is_admin:
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

        OBJECT_TYPE = cache.get('all_object_type_choices_json', [])
        if not OBJECT_TYPE:
            OBJECT_TYPE = [
                {"value": "other", "title": "Other"}
            ]

            all_object_types = ObjectType.objects.order_by('name').values_list('name', flat=True).distinct()
            for o in all_object_types:
                OBJECT_TYPE.append({"value": o, "title": o.title()})
            cache.set('all_object_type_choices_json', OBJECT_TYPE, 3600)
        self.response_format["object_types"] = OBJECT_TYPE

        return Response(self.response_format)

    def destroy(self, request, *args, **kwargs):
        crowdsource_image = self.get_object()
        delete_object(crowdsource_image.bucket_key())
        crowdsource_image.file.delete()
        return super().destroy(request, *args, **kwargs)

# PRUNE old ImageShare requests (check and remove old > 60 days requests)
def prune_old_image_share():
    if not cache.get('prune_image_share'):
        ImageShare.objects.filter(created_at__lte=timezone.now()-timedelta(days=60)).delete()
        cache.set("prune_image_share", True, 86400) # Prune every 24 hours

# Image Share Views
@login_required(login_url=login_url)
def images_share(request):
    prune_old_image_share();
    if request.method == "GET":
        images_share = []
        query = request.GET.get('q', '')
        if request.user and not request.user.is_anonymous:
            if (is_admin(request.user)):
                images_share = ImageShare.objects.order_by(
                    '-created_at').filter(Q(object_type__icontains=query) |
                                        Q(remarks__icontains=query) |
                                        Q(status__icontains=query)).distinct().all()
            else:
                images_share = ImageShare.objects.filter(
                    user=request.user).order_by('-created_at').filter(Q(object_type__icontains=query) |
                                            Q(remarks__icontains=query) |
                                            Q(status__icontains=query)).distinct().all()

            paginator = Paginator(images_share, 50)  # Show 50
            page_number = request.GET.get('page', '1')
            images = paginator.get_page(page_number)
        else:
            images = False

        form = ImageShareForm(request=request)
        return render(request, 'images_share.html',
                      {'images_share': images, 'form': form, 'query': query})
    elif request.method == "POST":
        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # EDIT
            try:
                if (is_admin(request.user)):
                    share_image = ImageShare.objects.filter(id=request.POST.get('id')).get()
                else:
                    share_image = ImageShare.objects.filter(user=request.user).filter(id=request.POST.get('id')).get()
                    if not share_image.status == "pending":
                        messages.error(request, "Image Request has already been " + share_image.status.title() + ". It cannot be edited now.")
                        return redirect("images_share")

                form = ImageShareForm(
                    request.POST or None, instance=share_image, request=request)
                if form.is_valid():
                    form.save()
                    messages.success(
                        request, "Image Request Updated Successfully")
                    return redirect("images_share")
            except ImageShare.DoesNotExist:
                pass
        else:
            # CREATE
            form = ImageShareForm(request.POST or None, request=request)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.user = request.user
                instance.save()
                messages.success(
                    request, "Image Request Created Successfully")
                return redirect("images_share")
        
        messages.error(request, "Invalid Request")
        return redirect("images_share")


def images_share_delete(request, id):
    if request.method == "POST":
        try:
            if request.user.is_admin:
                image = ImageShare.objects.filter(id=id).get()
            else:
                image = ImageShare.objects.filter(user=request.user).filter(id=id).get()

            if image:
                image.delete()
                messages.success(
                    request, 'Image Request Deleted Successfully!')
                return redirect("images_share")
        except ImageShare.DoesNotExist:
            pass

    messages.error(request, "Invalid Request")
    return redirect("images_share")
