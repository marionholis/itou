# Generated by Django 3.2.7 on 2021-12-14 09:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("approvals", "0021_approval_create_employee_record"),
    ]

    operations = [
        migrations.AlterField(
            model_name="approval",
            name="create_employee_record",
            field=models.BooleanField(default=True, verbose_name="Création d'une fiche salarié"),
        ),
    ]
