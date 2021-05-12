# Generated by Django 3.1.8 on 2021-05-12 13:38

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("job_applications", "0029_auto_20210223_1528"),
        ("employee_record", "0007_auto_20210505_1609"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employeerecord",
            name="job_application",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employee_record",
                to="job_applications.jobapplication",
                verbose_name="Candidature / embauche",
            ),
        ),
    ]
