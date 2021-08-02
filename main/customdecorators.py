from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from honeypot.decorators import check_honeypot


def admin_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url='login'):
    '''
    Decorator for views that checks that the logged in user is a admin,
    redirects to the log-in page if necessary.
    '''
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_admin,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator

def check_honeypot_conditional(function):
    '''
    Decorator to conditionally run Check Honeypot,
    Do not check honeypot when in testing mode. (Fixes its Bug)
    '''
    if settings.TESTING:
        # We do not apply the decorator (@check_honeypot) to the function
        return function
    else:
        # We apply the decorator and return the new function
        return check_honeypot()(function)