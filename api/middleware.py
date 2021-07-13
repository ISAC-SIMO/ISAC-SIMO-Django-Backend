import os

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.urls import resolve
import datetime

# Check for Maintenance Mode
class MaintenanceMode(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_url = resolve(request.path_info).url_name
        if current_url in ['pull','serviceworker','offline','index']:
            return self.get_response(request)
        
        if (hasattr(settings, 'MAINTENANCE') and settings.MAINTENANCE) or ("MAINTENANCE" in os.environ and os.getenv('MAINTENANCE') == 'True'):
            if '/api/' in str(request.build_absolute_uri()):
                return JsonResponse({'status':'false','message':'Maintenance Mode is active. Try later.','time':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, status=503)
            else:
                return render(request, 'master/maintenance.html', status=503)

        return self.get_response(request)

    # To ignore and throw default exception for any error
    # def process_exception(self, request, exception):
    #     return HttpResponse(exception)
