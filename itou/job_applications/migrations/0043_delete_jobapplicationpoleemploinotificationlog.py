# Generated by Django 4.0.4 on 2022-06-01 12:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("job_applications", "0042_added_transfer_fields"),
    ]

    operations = [
        migrations.DeleteModel(
            name="JobApplicationPoleEmploiNotificationLog",
        ),
    ]
