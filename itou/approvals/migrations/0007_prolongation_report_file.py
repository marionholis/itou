# Generated by Django 4.1.9 on 2023-06-15 13:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prescribers", "0003_alter_prescribermembership_updated_at_and_more"),
        ("files", "0001_initial"),
        ("approvals", "0006_alter_prolongation_updated_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="prolongation",
            name="contact_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="E-mail de contact"),
        ),
        migrations.AddField(
            model_name="prolongation",
            name="contact_phone",
            field=models.CharField(blank=True, max_length=20, verbose_name="Numéro de téléphone de contact"),
        ),
        migrations.AddField(
            model_name="prolongation",
            name="prescriber_organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="prescribers.prescriberorganization",
                verbose_name="Organisation du prescripteur habilité",
            ),
        ),
        migrations.AddField(
            model_name="prolongation",
            name="report_file",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="files.file",
                verbose_name="Fichier bilan",
            ),
        ),
        migrations.AddField(
            model_name="prolongation",
            name="require_phone_interview",
            field=models.BooleanField(blank=True, default=False, verbose_name="Demande d'entretien téléphonique"),
        ),
        migrations.AlterField(
            model_name="prolongation",
            name="reason",
            field=models.CharField(
                choices=[
                    ("SENIOR_CDI", "CDI conclu avec une personne de plus de 57\u202fans"),
                    ("COMPLETE_TRAINING", "Fin d'une formation"),
                    ("RQTH", "RQTH - Reconnaissance de la qualité de travailleur handicapé"),
                    ("SENIOR", "50\u202fans et plus"),
                    (
                        "PARTICULAR_DIFFICULTIES",
                        "Difficultés particulières qui font obstacle à l'insertion durable dans l’emploi",
                    ),
                    ("HEALTH_CONTEXT", "Contexte sanitaire"),
                ],
                default="COMPLETE_TRAINING",
                max_length=30,
                verbose_name="Motif",
            ),
        ),
        migrations.AddConstraint(
            model_name="prolongation",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("report_file", None),
                    models.Q(
                        ("reason__in", ("RQTH", "SENIOR", "PARTICULAR_DIFFICULTIES")), ("report_file__isnull", False)
                    ),
                    _connector="OR",
                ),
                name="reason_report_file_coherence",
                violation_error_message="Incohérence entre le fichier de bilan et la raison de prolongation",
            ),
        ),
    ]
