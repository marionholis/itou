# Generated by Django 4.1.8 on 2023-06-09 13:40

import django.db.models.deletion
from django.db import migrations, models

import itou.siae_evaluations.models


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0006_update_institution_kind"),
        ("siae_evaluations", "0004_evaluatedsiae_submission_freezed_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluationcampaign",
            name="institution",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="evaluation_campaigns",
                to="institutions.institution",
                validators=[itou.siae_evaluations.models.validate_institution],
                verbose_name="DDETS IAE responsable du contrôle",
            ),
        ),
    ]
