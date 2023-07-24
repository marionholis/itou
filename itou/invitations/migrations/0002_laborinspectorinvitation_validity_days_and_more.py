# Generated by Django 4.2.3 on 2023-07-24 10:03

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invitations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="laborinspectorinvitation",
            name="validity_days",
            field=models.PositiveSmallIntegerField(
                default=14,
                validators=[
                    django.core.validators.MinValueValidator(14),
                    django.core.validators.MaxValueValidator(90),
                ],
                verbose_name="durée de validité en jours",
            ),
        ),
        migrations.AddField(
            model_name="prescriberwithorginvitation",
            name="validity_days",
            field=models.PositiveSmallIntegerField(
                default=14,
                validators=[
                    django.core.validators.MinValueValidator(14),
                    django.core.validators.MaxValueValidator(90),
                ],
                verbose_name="durée de validité en jours",
            ),
        ),
        migrations.AddField(
            model_name="siaestaffinvitation",
            name="validity_days",
            field=models.PositiveSmallIntegerField(
                default=14,
                validators=[
                    django.core.validators.MinValueValidator(14),
                    django.core.validators.MaxValueValidator(90),
                ],
                verbose_name="durée de validité en jours",
            ),
        ),
    ]
