from django.db import models


# Create your models here.
class Projects(models.Model):
    project_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='project_images')
    project_desc = models.TextField()
    detect_model = models.TextField(blank=True, null=True)
    offline_model = models.ForeignKey('api.OfflineModel', on_delete=models.SET_NULL, related_name='projects',
                                      blank=True, null=True)
    guest = models.BooleanField(default=False)  # Guest=True for Global project
    ibm_api_key = models.CharField(max_length=200, blank=True, null=True)
    ibm_service_url = models.CharField(max_length=200, blank=True, null=True)
    public = models.BooleanField(default=False)  # Is this Project Publically Visible
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.project_name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Call the "real" save() method.

    def unique_name(self):
        return self.project_name.lower() + '-' + str(self.id)

    def get_ibm_service_url(self):
        if self.ibm_service_url:
            return self.ibm_service_url
        return "https://api.us-south.visual-recognition.watson.cloud.ibm.com"
