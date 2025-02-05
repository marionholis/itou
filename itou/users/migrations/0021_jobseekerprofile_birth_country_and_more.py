# Generated by Django 4.2.4 on 2023-08-31 09:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("asp", "0002_commune_created_by"),
        ("users", "0020_user_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobseekerprofile",
            name="birth_country",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="jobseeker_profiles_born_here",
                to="asp.country",
                verbose_name="pays de naissance",
            ),
        ),
        migrations.AddField(
            model_name="jobseekerprofile",
            name="birth_place",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="jobseeker_profiles_born_here",
                to="asp.commune",
                verbose_name="commune de naissance",
            ),
        ),
    ]
