"""isac_simo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from crowdsource.views import CrowdsourceView, ImageShareView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework import routers
from rest_framework_simplejwt.views import (TokenObtainPairView,
                                            TokenRefreshView)

from api import views as api
from api.views import ClassifierView, ContributionView, FileUploadView, ImageView, ObjectTypeView, OfflineModelView, ProfileView, ProjectView, UserView, VideoFrameView, clean_temp_view, fetch_classifier_detail, fetch_object_type_detail, fulcrum, kobo, retrain_classifier, terminal_view, test_view
from main import views
from django.conf.urls.i18n import i18n_patterns


router = routers.DefaultRouter()
router.register('register', UserView)
router.register('user', UserView)
router.register('image', ImageView)
router.register('profile', ProfileView)
router.register('video', VideoFrameView)
router.register('project', ProjectView)
router.register('object', ObjectTypeView)
router.register('classifier', ClassifierView)
router.register('offline_model', OfflineModelView)
router.register('file', FileUploadView)
router.register('crowdsource', CrowdsourceView)
router.register('images-share', ImageShareView)
router.register(r'object/(?P<object_id>.+)/contribution', ContributionView)

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    # API
    path('api/user/', include('rest_framework.urls')), # REST_FRAMEWORK_URL_FOR_TEST
    path('api/auth/', TokenObtainPairView.as_view(), name='auth'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='auth_refresh'),
    path('api/', include(router.urls)),
    path('api/ping/', test_view, name='test_view'),
    path('api/terminal/', terminal_view, name='terminal_view'),
    path('api/clean_temp/', clean_temp_view, name='clean_temp_view'),
    path('api/detail/classifier/', fetch_classifier_detail, name='fetch_classifier_detail'), # Classifier Detail Fetch API
    path('api/detail/object_type/', fetch_object_type_detail, name='fetch_object_type_detail'), # Object Type Detail Fetch API
    path('api/retrain/classifier/', retrain_classifier, name='retrain_classifier'), # Re-Train Classifier
    path('api/kobo/', kobo, name='kobo'), # Kobo Toolbox Webhook
    path('api/fulcrum/', fulcrum, name='fulcrum'), # Fulcrum Webhook
    # WEB
    path('', views.index, name="index"),
    path('login/', views.login_user, name="login"),
    path('login/<int:id>', views.login_user, name="loginpost"),
    path('register/', views.register, name="register"),
    path('logout/',  views.logout_user, name="logout"),
    re_path(r'^dashboard/?$', views.home, name="dashboard"),
    path('pull', views.pull, name="pull"), # Pull used by circleci trigger to deploy
    path('users/', include('main.urls')),
    path('projects/', include('projects.urls')),
    path('app/', include('api.urls')),
    path('map/', include('map.urls')),
    path('crowdsource/', include('crowdsource.urls')),
    # Service Worker js
    path('serviceworker.js', views.serviceworker, name="serviceworker"),
    path('offline', views.offline, name="offline"),
    path('translator/', include('main.translator.urls')),
    path('logs/', include('main.syslogger.urls')),
    path('privacy-policy/', views.privacy_policy, name="privacy_policy"),
]
# This is for further model field translation and other..
urlpatterns += i18n_patterns(

)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.DOCS_URL, document_root=settings.DOCS_ROOT)
    urlpatterns += path('admin/', admin.site.urls),
