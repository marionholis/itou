# Generated by Django 4.1.9 on 2023-06-12 10:23

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inclusion_connect", "0006_oidconnect_csrf_to_state"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inclusionconnectstate",
            name="csrf",
            field=models.CharField(max_length=12, null=True),
        ),
        migrations.AlterField(
            model_name="inclusionconnectstate",
            name="state",
            field=models.CharField(max_length=12, unique=True),
        ),
    ]
