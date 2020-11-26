from api.models import ObjectType
from django.core.cache import cache
from crowdsource.helpers import delete_object, get_object, move_object, upload_object
from crowdsource.forms import CrowdsourceForm
from crowdsource.models import Crowdsource
from django.shortcuts import get_object_or_404, redirect, render
from main.authorization import login_url, is_admin, is_admin_or_project_admin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import serializers
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from .serializers import CrowdsourceSerializer
from rest_framework.response import Response

# View All Crowdsource Images + Update/Create

@login_required(login_url=login_url)
def crowdsource_images(request):
    if request.method == "GET":
        crowdsource_images = []
        query = request.GET.get('q','')
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

        form = CrowdsourceForm()

        return render(request, 'crowdsource_images.html', {'crowdsources': crowdsources, 'form': form, 'query': query})
    elif request.method == "POST":
        if request.POST.get('id', False) and request.POST.get('id') != "0":
            # EDIT
            try:
                if(is_admin_or_project_admin(request.user)):
                    crowdsource_image = Crowdsource.objects.filter(
                        id=request.POST.get('id')).get()
                else:
                    crowdsource_image = Crowdsource.objects.filter(
                        created_by=request.user).filter(id=request.POST.get('id')).get()

                form = CrowdsourceForm(
                    request.POST or None, instance=crowdsource_image)
                old_object_key = crowdsource_image.bucket_key()
                if form.is_valid():
                    instance = form.save(commit=False)
                    instance.save()
                    if old_object_key != instance.bucket_key():
                        move_object(instance.bucket_key(), old_object_key)
                    messages.success(
                        request, "Crowdsource Image Updated Successfully")
                    return redirect("crowdsource")
            except(Crowdsource.DoesNotExist):
                pass
        else:
            # TODO: FOR NOW LIMIT 5 TOTAL UPLOADS BY SAME USER ( SAME BELOW )
            if(Crowdsource.objects.filter(created_by=request.user).count() >= 5):
                messages.error(request, "Currently you can only upload 5 images. More will be enabled later.")
                return redirect("crowdsource")

            # Create
            total = 0
            for _file in request.FILES.getlist('file'):
                request.FILES['file'] = _file
                form = CrowdsourceForm(
                    request.POST or None, request.FILES or None)
                if form.is_valid():
                    instance = form.save(commit=False)
                    instance.created_by = request.user
                    instance.save()
                    upload_object(instance.bucket_key(), instance.filepath())
                    total += 1
                    if total >= 5:
                        break; # TODO: FOR NOW LIMIT 5 TOTAL UPLOADS BY SAME USER

            messages.success(request, "Yay, " +str(total)+ " New Image(s) Contributed to Crowdsource.")
            return redirect("crowdsource")

    messages.error(request, "Invalid Request")
    return redirect("crowdsource")


@user_passes_test(is_admin, login_url=login_url)
def crowdsource_images_delete(request, id):
    if request.method == "POST":
        try:
            crowdsource_image = Crowdsource.objects.filter(id=id).get()
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
