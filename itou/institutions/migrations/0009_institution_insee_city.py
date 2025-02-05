# Generated by Django 4.2.5 on 2023-09-15 07:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cities", "0003_city_edition_mode"),
        ("institutions", "0008_alter_institution_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="insee_city",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="cities.city"
            ),
        ),
    ]
