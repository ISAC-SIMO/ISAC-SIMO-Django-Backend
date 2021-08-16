from django.urls import path

from . import views


urlpatterns = [
    path('', views.error_dashboard, name="error_log"),
    path('clear', views.clear_error, name="error_log_clear"),
]