# Generated by Django 4.1.4 on 2022-12-16 12:50

import django.contrib.postgres.indexes
from django.contrib.postgres.operations import (
    BtreeGistExtension,
    CITextExtension,
    CreateExtension,
    TrigramExtension,
    UnaccentExtension,
)
from django.db import migrations, models

import itou.asp.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        # Install PostgreSQL extensions
        # The 'asp' app has been chosen as entry point because it's central
        # dependency on the application and its migrations are processed early in the chain.
        BtreeGistExtension(),
        CITextExtension(),
        TrigramExtension(),
        CreateExtension("postgis"),
        UnaccentExtension(),
        migrations.RunSQL("DROP TEXT SEARCH CONFIGURATION IF EXISTS french_unaccent"),
        migrations.RunSQL("CREATE TEXT SEARCH CONFIGURATION french_unaccent (COPY = french)"),
        migrations.RunSQL(
            """
            ALTER TEXT SEARCH CONFIGURATION french_unaccent
                ALTER MAPPING FOR hword, hword_part, word
                    WITH unaccent, french_stem
            """
        ),
        migrations.CreateModel(
            name="Commune",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="début de validité")),
                ("end_date", models.DateField(blank=True, null=True, verbose_name="fin de validité")),
                ("code", models.CharField(db_index=True, max_length=5, verbose_name="code commune INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="nom de la commune")),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now, verbose_name="date de création"),
                ),
            ],
            options={
                "verbose_name": "commune",
            },
            bases=(itou.asp.models.PrettyPrintMixin, models.Model),
        ),
        migrations.CreateModel(
            name="Country",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=3, verbose_name="code pays INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="nom du pays")),
                (
                    "group",
                    models.CharField(
                        choices=[("1", "France"), ("2", "CEE"), ("3", "Hors CEE")],
                        max_length=15,
                        verbose_name="groupe",
                    ),
                ),
                ("department", models.CharField(default="098", max_length=3, verbose_name="code département")),
            ],
            options={
                "verbose_name": "pays",
                "verbose_name_plural": "pays",
                "ordering": ["name"],
            },
            bases=(itou.asp.models.PrettyPrintMixin, models.Model),
        ),
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="début de validité")),
                ("end_date", models.DateField(blank=True, null=True, verbose_name="fin de validité")),
                ("code", models.CharField(max_length=3, verbose_name="code département INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="nom du département")),
            ],
            options={
                "verbose_name": "département",
            },
            bases=(itou.asp.models.PrettyPrintMixin, models.Model),
        ),
        migrations.AddIndex(
            model_name="commune",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["name"], name="aps_communes_name_gin_trgm", opclasses=["gin_trgm_ops"]
            ),
        ),
    ]
