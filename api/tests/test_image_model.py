from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.staticfiles import finders
from api.models import Image, ImageFile, ObjectType, OfflineModel, Classifier, FileUpload, Contribution
from main.models import User
from projects.models import Projects


@override_settings(DEBUG=True)
class TestApiModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestApiModel, cls).setUpClass()
        # USER
        cls.user = User.objects.create_user(email="testuser@gmail.com", user_type="user", password="test@1234")

        # image and Image File
        cls.image = Image.objects.create(title="test title", description="test desc", user=cls.user, lat=26, lng=84)
        cls.file = finders.find('dist/img/avatar.png')
        cls.img_file = ImageFile.objects.create(image=cls.image, file=cls.file)
        cls.project = Projects.objects.create(project_name="test name", image=cls.file, project_desc="some description", guest=True, detect_model="lorem",
                                ibm_api_key="HEEDS-GARTH&-HNKJH",ibm_service_url="https://example.com", public=True)
        cls.object_type = ObjectType.objects.create(name="test name", created_by=cls.user, project=cls.project, image=cls.file,
                                                    instruction="test instruction", verified=True)
        cls.offline_model = OfflineModel.objects.create(name="test name", model_type="brick",model_format="test format", file=cls.file,
                                                        offline_model_labels="test label", created_by=cls.user,preprocess=True,postprocess=False)
        cls.classifier = Classifier.objects.create(name="test name", given_name="test given name",classes="test classes",project=cls.project,
                                                   object_type=cls.object_type,order=1,offline_model=cls.offline_model,is_object_detection=True,
                                                   ibm_api_key="HEEDS-GARTH&-HNKJH", ibm_service_url="https://example.com",created_by=cls.user)
        cls.file_upload = FileUpload.objects.create(name="Test name", file=cls.file, created_by=cls.user)
        cls.contribution = Contribution.objects.create(title="test title",description="some description", file=cls.file, object_type=cls.object_type,
                                                       is_helpful=False, created_by=cls.user)

    def setUp(self):
        self.user = TestApiModel.user
        self.image = TestApiModel.image
        self.file = TestApiModel.file
        self.img_file = TestApiModel.img_file
        self.project = TestApiModel.project
        self.object_type = TestApiModel.object_type
        self.offline_model = TestApiModel.offline_model
        self.classifier = TestApiModel.classifier
        self.file_upload = TestApiModel.file_upload
        self.contribution = TestApiModel.contribution

    def test_image_created(self):
        self.assertEqual(Image.objects.count(), 1)

    def test_image_file_created(self):
        self.assertEqual(ImageFile.objects.count(), 1)

    def test_project_created(self):
        self.assertEqual(Projects.objects.count(), 1)

    def test_object_type_created(self):
        self.assertEqual(ObjectType.objects.count(), 1)

    def test_offline_model_created(self):
        self.assertEqual(OfflineModel.objects.count(), 1)

    def test_classifier_created(self):
        self.assertEqual(Classifier.objects.count(), 1)

    def test_file_upload_created(self):
        self.assertEqual(FileUpload.objects.count(), 1)

    def test_contribution_created(self):
        self.assertEqual(Contribution.objects.count(), 1)
