import json
from django.conf import settings
from api.models import Classifier, ObjectType, OfflineModel
from projects.models import Projects
from main.models import User
from django.test import TestCase
import isac_simo.classifier_list as classifier_list


class ClassifierList(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ClassifierList, cls).setUpClass()
        # USER
        cls.user = User.objects.create(
          full_name='user', email='project_admin@example.com',
          password='secret', user_type='project_admin', is_staff=False, active=True
        )

        # PROJECT
        cls.project = Projects.objects.create(
          id=1,
          project_name='My Project 1', image="image.jpg",
          project_desc='My Project 1 Description', guest=True
        )

        # Assign User the Project
        cls.user.projects.add(cls.project)

        # OBJECT TYPE
        cls.object_type = ObjectType.objects.create(
          name='wall', created_by=cls.user,
          project=cls.project, 
          instruction="A instruction on how to test image properly."
        )

        # OFFLINE MODEL
        cls.offline_model = OfflineModel.objects.create(
          name='wall-post-process-1', model_type='CLASSIFIER',
          model_format="py", file="wall-post-process-1.py",
          preprocess=True, postprocess=False,
          created_by=cls.user,
        )

        # CLASSIFIER
        cls.classifier = Classifier.objects.create(
          name='wall-post-process-1', given_name='wall-post-process-1',
          project=cls.project, object_type=cls.object_type,
          order=1, offline_model=cls.offline_model,
          created_by=cls.user
        )

    def setUp(self):
        self.user = ClassifierList.user
        self.project = ClassifierList.project
        self.object_type = ClassifierList.object_type
        self.offline_model = ClassifierList.offline_model
        self.classifier = ClassifierList.classifier

    def test_classifier_list_data(self):
        """
        The classifier_list.data should return data as expected (Core App Logic is mostly here for distinguish project, object and classifiers uniquely)
        """
        classifier_list_data = classifier_list.data()
        self.assertEqual(len(classifier_list_data), 1)
        self.assertDictEqual(classifier_list_data, {
          'my project 1-1': {
            'wall': ['wall-post-process-1']
          }
        })

    def test_classifier_list_value(self):
        """
        The classifier_list.value should return classifier_list.data() from cache as expected.
        We need to run classifier_list.data() first so that this instance of test is receiving our own setUp data.
        Without running that function first, as we are auto-loading classifier_list.py, it returns original cache (i.e. real data)
        """
        classifier_list.data()
        self.assertRegex(json.dumps(settings.CACHES), "DummyCache")
        self.assertDictEqual(classifier_list.value(), {
          'my project 1-1': {
            'wall': ['wall-post-process-1']
          }
        })

    def test_classifier_list_lenList(self):
        """
        The classifier_list.lenList() takes project and its object_type. Then, returns the length of specific object (i.e. total pipeline steps) 
        We need to run classifier_list.data() first so that this instance of test is receiving our own setUp data.
        Without running that function first, as we are auto-loading classifier_list.py, it returns original cache (i.e. real data)
        """
        classifier_list.data()
        classifier_list_lenList = classifier_list.lenList(self.project.unique_name(), self.object_type.name.lower())
        self.assertEqual(classifier_list_lenList, 1)

    def test_classifier_list_searchList(self):
        """
        The classifier_list.searchList() takes project and its object_type. And, optionally either model name or index.
        Then, returns model name if provided model or index exists in that project's object_type pipelines (else return False)
        We need to run classifier_list.data() first so that this instance of test is receiving our own setUp data.
        Without running that function first, as we are auto-loading classifier_list.py, it returns original cache (i.e. real data)
        """
        classifier_list.data()
        classifier_list_searchList_by_model = classifier_list.searchList(self.project.unique_name(), self.object_type.name.lower(), model=self.classifier.name)
        self.assertEqual(classifier_list_searchList_by_model, "wall-post-process-1")

        classifier_list_searchList_by_index = classifier_list.searchList(self.project.unique_name(), self.object_type.name.lower(), index=0)
        self.assertEqual(classifier_list_searchList_by_index, "wall-post-process-1")

        classifier_list_searchList_non_existing_index = classifier_list.searchList(self.project.unique_name(), self.object_type.name.lower(), index=1)
        self.assertEqual(classifier_list_searchList_non_existing_index, False)