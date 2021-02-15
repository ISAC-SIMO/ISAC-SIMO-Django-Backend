# Generated by Django 2.0 on 2020-12-02 10:25

import api.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0033_contribution'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contribution',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to=api.models.PathAndRename('contributions')),
        ),
    ]