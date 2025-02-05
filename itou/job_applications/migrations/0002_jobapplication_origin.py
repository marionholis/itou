# Generated by Django 4.1.5 on 2023-01-26 10:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("job_applications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobapplication",
            name="origin",
            field=models.CharField(
                choices=[
                    ("default", "Créée normalement via les emplois"),
                    ("pe_approval", "Créée lors d'un import d'Agrément Pole Emploi"),
                    ("ai_stock", "Créée lors de l'import du stock AI"),
                    ("admin", "Créée depuis l'admin"),
                ],
                default="default",
                max_length=30,
                verbose_name="origine de la candidature",
            ),
        ),
    ]
