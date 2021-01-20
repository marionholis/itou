# flake8: noqa
# Generated by Django 3.1.4 on 2021-01-20 09:36

import django.db.models.deletion
import django.db.models.manager
from django.db import migrations, models

import itou.asp.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Commune",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="Début de validité")),
                ("end_date", models.DateField(null=True, verbose_name="Fin de validité")),
                ("code", models.CharField(max_length=5, verbose_name="Code commune INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="Nom de la commune")),
            ],
            options={"abstract": False,},
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
            managers=[("current", django.db.models.manager.Manager()),],
        ),
        migrations.CreateModel(
            name="Country",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=3, verbose_name="Code pays INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="Nom du pays")),
                ("group", models.CharField(choices=[("1", "France"), ("2", "CEE"), ("3", "Hors CEE")], max_length=15)),
                ("department", models.CharField(default="098", max_length=3, verbose_name="Code département")),
            ],
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
        ),
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="Début de validité")),
                ("end_date", models.DateField(null=True, verbose_name="Fin de validité")),
                ("code", models.CharField(max_length=3, verbose_name="Code département INSEE")),
                ("name", models.CharField(max_length=50, verbose_name="Nom du département")),
            ],
            options={"abstract": False,},
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
            managers=[("current", django.db.models.manager.Manager()),],
        ),
        migrations.CreateModel(
            name="EducationLevel",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="Début de validité")),
                ("end_date", models.DateField(null=True, verbose_name="Fin de validité")),
                ("code", models.CharField(max_length=2, verbose_name="Code formation ASP")),
                ("name", models.CharField(max_length=80, verbose_name="Libellé niveau de formation ASP")),
            ],
            options={"abstract": False,},
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
            managers=[("current", django.db.models.manager.Manager()),],
        ),
        migrations.CreateModel(
            name="Measure",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="Début de validité")),
                ("end_date", models.DateField(null=True, verbose_name="Fin de validité")),
                ("code", models.CharField(max_length=10, verbose_name="Code mesure ASP complet")),
                ("display_code", models.CharField(max_length=5, verbose_name="Code mesure ASP resumé")),
                ("help_code", models.CharField(max_length=5, verbose_name="Code d'aide mesure ASP")),
                ("name", models.CharField(max_length=80, verbose_name="Libellé mesure ASP")),
                ("rdi_id", models.CharField(max_length=1, verbose_name="Identifiant RDI ?")),
            ],
            options={"abstract": False,},
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
            managers=[("current", django.db.models.manager.Manager()),],
        ),
        migrations.CreateModel(
            name="EmployerType",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="Début de validité")),
                ("end_date", models.DateField(null=True, verbose_name="Fin de validité")),
                ("code", models.CharField(max_length=3, verbose_name="Code employeur ASP")),
                ("name", models.CharField(max_length=50, verbose_name="Libellé employeur ASP")),
                (
                    "measure",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="asp.measure",
                        verbose_name="Mesure ASP",
                    ),
                ),
            ],
            options={"abstract": False,},
            bases=(itou.asp.models.NameLabelStrMixin, models.Model),
            managers=[("current", django.db.models.manager.Manager()),],
        ),
    ]
