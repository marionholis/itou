# Generated by Django 4.2.5 on 2023-09-20 16:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0023_remove_user_birth_country_remove_user_birth_place"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobseekerprofile",
            name="birth_country",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="jobseeker_profiles_born_here",
                to="asp.country",
                verbose_name="pays de naissance",
            ),
        ),
        migrations.AlterField(
            model_name="jobseekerprofile",
            name="birth_place",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="jobseeker_profiles_born_here",
                to="asp.commune",
                verbose_name="commune de naissance",
            ),
        ),
        migrations.AlterField(
            model_name="jobseekerprofile",
            name="hexa_commune",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                to="asp.commune",
                verbose_name="commune (ref. ASP)",
            ),
        ),
    ]
