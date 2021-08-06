from django.test import TestCase
from django.urls import resolve, reverse
from . import views
from django.contrib.staticfiles import finders
from .models import Projects
from .forms import ProjectForm
from django.core.files.uploadedfile import SimpleUploadedFile


class TestProjectsUrl(TestCase):

    def test_project_view_resloved(self):
        url = reverse('viewprojects')
        self.assertEqual(resolve(url).func, views.viewProjects)

    def test_project_addproject_resloved(self):
        url = reverse('addproject')
        self.assertEqual(resolve(url).func, views.addProject)

    def test_project_update_resloved(self):
        url = reverse('updateproject', args=[2])
        self.assertEqual(resolve(url).func, views.editProject)

    def test_project_delete_resloved(self):
        url = reverse('deleteproject', args=[5])
        self.assertEqual(resolve(url).func, views.deleteProject)

    def test_public_projects_resloved(self):
        url = reverse('public_projects')
        self.assertEqual(resolve(url).func, views.publicProjects)

    def test_public_project_join_resloved(self):
        url = reverse('public_project_join', args=[10])
        self.assertEqual(resolve(url).func, views.publicProjectJoin)

    def test_public_project_info_resloved(self):
        url = reverse('public_project_info', args=[1])
        self.assertEqual(resolve(url).func, views.publicProjectInfo)

    def test_contribution_resloved(self):
        url = reverse('contribution', args=[7, 9])
        self.assertEqual(resolve(url).func, views.addContribution)

    def test_delete_contribution_resloved(self):
        url = reverse('delete.contribution', args=[7, 9, 3])
        self.assertEqual(resolve(url).func, views.deleteContribution)


class TestProjectsModel(TestCase):
    def setUp(self):
        file = finders.find('dist/img/avatar.png')
        Projects.objects.create(project_name="test name", image=file, project_desc="some description", guest=True,
                                detect_model="lorem",
                                ibm_api_key="HEEDS-GARTH&-HNKJH", ibm_service_url="https://example.com", public=True)

    def test_project_created(self):
        self.assertEqual(Projects.objects.count(), 1)


class TestProjectForms(TestCase):
    def test_project_form(self):
        f = open(finders.find('dist/img/avatar.png'), 'rb').read()
        upload_file={
            "image": SimpleUploadedFile(name='avatar.png', content=f, content_type='image/png')
        }
        form_data = {
            "project_name": "test name",
            "project_desc": "This is test project",
            "detect_model": "development",
            "ibm_service_url": "https://example.com",
            "ibm_api_key": "HEEDS-GARTH&-HNKJH",
            "public": True

        }

        form = ProjectForm(data=form_data, files=upload_file)
        self.assertTrue(form.is_valid())
