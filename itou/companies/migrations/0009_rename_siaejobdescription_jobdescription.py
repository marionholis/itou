# Generated by Django 4.2.7 on 2023-11-06 09:36

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cities", "0001_initial"),
        ("jobs", "0001_initial"),
        ("job_applications", "0018_alter_jobapplication_sender_siae_and_more"),
        ("companies", "0008_rename_siaemembership_companymembership"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="SiaeJobDescription",
            new_name="JobDescription",
        ),
    ]
