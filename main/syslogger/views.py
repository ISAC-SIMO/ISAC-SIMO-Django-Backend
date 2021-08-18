from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect

from main.authorization import is_admin, login_url
from django.conf import settings


@user_passes_test(is_admin, login_url=login_url)
def error_dashboard(request):
    file = settings.SYSLOG_PATHS
    f = open('{}/errors.log'.format(file[0]), "r")
    list_items = f.read().split('\nERROR ')
    args = {'result': list_items}
    return render(request, "syslogs.html", args)


@user_passes_test(is_admin, login_url=login_url)
def clear_error(request):
    file = settings.SYSLOG_PATHS
    with open('{}/errors.log'.format(file[0]), 'w'): pass
    return redirect('error_log')
