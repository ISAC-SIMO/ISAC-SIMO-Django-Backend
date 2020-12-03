from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.viewProjects, name="viewprojects"),
    path('add', views.addProject, name="addproject"),
    path('update/<int:id>', views.editProject, name="updateproject"),
    path('delete/<int:id>', views.deleteProject, name="deleteproject"),
    path('test/offline/<int:id>', views.testOfflineProject, name="testofflineproject"),
    path('public', views.publicProjects, name="public_projects"),
    path('public/join/<int:id>', views.publicProjectJoin, name="public_project_join"),
    path('public/<int:id>', views.publicProjectInfo, name="public_project_info"),
    path('public/<int:id>/object/<int:object_id>/contribution', views.addContribution, name="contribution"),
    path('public/<int:id>/object/<int:object_id>/contribution/delete/<int:contribution_id>', views.deleteContribution, name="delete.contribution"),
]