# Generated by Django 4.1.5 on 2023-01-30 15:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("job_applications", "0004_make_jobapplication_created_from_pe_approval_nullable"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="jobapplication",
            name="created_from_pe_approval",
        ),
    ]
