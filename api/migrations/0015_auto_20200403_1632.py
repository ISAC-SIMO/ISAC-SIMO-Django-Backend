# Generated by Django 2.0 on 2020-04-03 10:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_auto_20200403_1510'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classifier',
            name='classes',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='given_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='name',
            field=models.CharField(max_length=200),
        ),
    ]