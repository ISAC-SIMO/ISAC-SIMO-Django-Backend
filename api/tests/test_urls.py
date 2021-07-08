from django.test import TestCase
from django.urls import resolve, reverse
from .. import views


class TestImageRelatedUrl(TestCase):

    def test_images_resloved(self):
        url = reverse('images')
        self.assertEqual(resolve(url).func, views.images)

    def test_add_image_resloved(self):
        url = reverse('images.add')
        self.assertEqual(resolve(url).func, views.addImage)

    def test_testing_image_resloved(self):
        url = reverse('images.test')
        self.assertEqual(resolve(url).func, views.testImage)

    def test_update_image_resloved(self):
        url = reverse('images.update', args=[3])
        self.assertEqual(resolve(url).func, views.updateImage)

    def test_delete_image_resloved(self):
        url = reverse('images.delete', args=[3])
        self.assertEqual(resolve(url).func, views.deleteImage)

    def test_retrain_image_resloved(self):
        url = reverse('images.retrain', args=[3])
        self.assertEqual(resolve(url).func, views.retrainImage)

    def test_delete_imagefile_resloved(self):
        url = reverse('images.image_file.delete', args=[3])
        self.assertEqual(resolve(url).func, views.deleteImageFile)

    def test_delete_imagefile_retest_resloved(self):
        url = reverse('images.image_file.retest', args=[3])
        self.assertEqual(resolve(url).func, views.retestImageFile)

    def test_delete_imagefile_verify_resloved(self):
        url = reverse('images.image_file.verify', args=[3])
        self.assertEqual(resolve(url).func, views.verifyImageFile)


class TestWatsonClassifierUrl(TestCase):

    def test_watson_classifier_list_resloved(self):
        url = reverse('watson.classifier.list')
        self.assertEqual(resolve(url).func, views.watsonClassifierList)

    def test_watson_classifier_order_resloved(self):
        url = reverse('watson.classifier.order', args=[3])
        self.assertEqual(resolve(url).func, views.watsonClassifierOrder)

    def test_watson_classifier_create_resloved(self):
        url = reverse('watson.classifier.create')
        self.assertEqual(resolve(url).func, views.watsonClassifierCreate)

    def test_watson_classifier_delete_resloved(self):
        url = reverse('watson.classifier.delete', args=[3])
        self.assertEqual(resolve(url).func, views.watsonClassifierDelete)

    def test_watson_classifier_edit_resloved(self):
        url = reverse('watson.classifier.edit', args=[3])
        self.assertEqual(resolve(url).func, views.watsonClassifierEdit)

    def test_watson_classifier_test_resloved(self):
        url = reverse('watson.classifier.test', args=[3])
        self.assertEqual(resolve(url).func, views.watsonClassifierTest)

    def test_watson_classifier_detail_resloved(self):
        url = reverse('watson.classifier')
        self.assertEqual(resolve(url).func, views.watsonClassifier)

    def test_watson_classifier_train_resloved(self):
        url = reverse('watson.train')
        self.assertEqual(resolve(url).func, views.watsonTrain)

    def test_watson_object_list_resloved(self):
        url = reverse('watson.object.list')
        self.assertEqual(resolve(url).func, views.watsonObjectList)

    def test_watson_object_create_resloved(self):
        url = reverse('watson.object.create')
        self.assertEqual(resolve(url).func, views.watsonObjectCreate)

    def test_watson_object_delete_resloved(self):
        url = reverse('watson.object.delete', args=[2])
        self.assertEqual(resolve(url).func, views.watsonObjectDelete)

    def test_watson_object_verify_resloved(self):
        url = reverse('watson.object.verify', args=[1])
        self.assertEqual(resolve(url).func, views.watsonObjectVerify)

    def test_watson_object_wishlist_resloved(self):
        url = reverse('watson.object.wishlist', args=[4])
        self.assertEqual(resolve(url).func, views.watsonObjectWishlist)

    def test_watson_object_detail_resloved(self):
        url = reverse('watson.object')
        self.assertEqual(resolve(url).func, views.watsonObject)


class TestOfflineModelUrl(TestCase):

    def test_offline_model_list_resloved(self):
        url = reverse('offline.model.list')
        self.assertEqual(resolve(url).func, views.offlineModel)

    def test_offline_model_create_resloved(self):
        url = reverse('offline.model.create')
        self.assertEqual(resolve(url).func, views.offlineModelCreate)

    def test_offline_model_edit_resloved(self):
        url = reverse('offline.model.edit', args=[4])
        self.assertEqual(resolve(url).func, views.offlineModelEdit)

    def test_offline_model_delete_resloved(self):
        url = reverse('offline.model.delete', args=[4])
        self.assertEqual(resolve(url).func, views.offlineModelDelete)

    def test_offline_model_test_resloved(self):
        url = reverse('offline.model.test', args=[4])
        self.assertEqual(resolve(url).func, views.offlineModelTest)

    def test_offline_model_dependency_resloved(self):
        url = reverse('offline.model.dependencies', args=[4])
        self.assertEqual(resolve(url).func, views.offlineModelDependencies)

    def test_offline_model_readme_resloved(self):
        url = reverse('offline.model.readme')
        self.assertEqual(resolve(url).func, views.offlineModelReadme)


class TestOtherActionUrl(TestCase):

    def test_cleantemp_resloved(self):
        url = reverse('watson.cleantemp')
        self.assertEqual(resolve(url).func, views.cleanTemp)

    def test_cleantempstreetview_resloved(self):
        url = reverse('watson.cleantempstreetview')
        self.assertEqual(resolve(url).func, views.cleanTempStreetView)

    def test_countimage_resloved(self):
        url = reverse('watson.countimage')
        self.assertEqual(resolve(url).func, views.countImage)

    def test_dumpimage_resloved(self):
        url = reverse('watson.dumpimage')
        self.assertEqual(resolve(url).func, views.dumpImage)

    def test_terminal_resloved(self):
        url = reverse('terminal')
        self.assertEqual(resolve(url).func, views.terminal)

    def test_file_upload_resloved(self):
        url = reverse('file_upload')
        self.assertEqual(resolve(url).func, views.fileUpload)

    def test_file_upload_delete_resloved(self):
        url = reverse('file_upload.delete', args=[1])
        self.assertEqual(resolve(url).func, views.fileUploadDelete)
