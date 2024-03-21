# Generated by Django 5.0.3 on 2024-03-21 08:48

import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("companies", "0009_rename_siaejobdescription_jobdescription"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyApiToken",
            fields=[
                ("key", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "label",
                    models.CharField(
                        max_length=60, unique=True, verbose_name="mémo permettant d'identifier l'usage du jeton"
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("companies", models.ManyToManyField(related_name="api_tokens", to="companies.company")),
            ],
            options={
                "verbose_name": "jeton d'API SIAE",
                "verbose_name_plural": "jetons d'API SIAE",
            },
        ),
    ]
