# Generated by Django 4.1.4 on 2022-12-16 12:28

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import itou.siae_evaluations.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("companies", "0001_initial"),
        ("job_applications", "0001_initial"),
        ("institutions", "0001_initial"),
        ("eligibility", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationCampaign",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="nom de la campagne d'évaluation")),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now, verbose_name="date de création"),
                ),
                (
                    "percent_set_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="date de paramétrage de la sélection"),
                ),
                (
                    "evaluations_asked_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date de notification du contrôle aux Siaes"
                    ),
                ),
                (
                    "ended_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="date de clôture de la campagne"),
                ),
                ("evaluated_period_start_at", models.DateField(verbose_name="date de début de la période contrôlée")),
                ("evaluated_period_end_at", models.DateField(verbose_name="date de fin de la période contrôlée")),
                (
                    "chosen_percent",
                    models.PositiveIntegerField(
                        default=30,
                        validators=[
                            django.core.validators.MinValueValidator(20),
                            django.core.validators.MaxValueValidator(40),
                        ],
                        verbose_name="pourcentage de sélection",
                    ),
                ),
                (
                    "institution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluation_campaigns",
                        to="institutions.institution",
                        validators=[itou.siae_evaluations.models.validate_institution],
                        verbose_name="DDETS responsable du contrôle",
                    ),
                ),
            ],
            options={
                "verbose_name": "campagne",
                "ordering": ["-name", "institution__name"],
            },
        ),
        migrations.CreateModel(
            name="EvaluatedSiae",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "evaluation_campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_siaes",
                        to="siae_evaluations.evaluationcampaign",
                        verbose_name="contrôle",
                    ),
                ),
                (
                    "siae",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_siaes",
                        to="companies.siae",
                        verbose_name="SIAE",
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True, verbose_name="contrôlée le")),
                (
                    "final_reviewed_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="contrôle définitif le"),
                ),
                (
                    "notification_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("DELAY", "Non respect des délais"),
                            ("INVALID_PROOF", "Pièce justificative incorrecte"),
                            ("MISSING_PROOF", "Pièce justificative manquante"),
                            ("OTHER", "Autre"),
                        ],
                        max_length=255,
                        null=True,
                        verbose_name="raison principale",
                    ),
                ),
                ("notification_text", models.TextField(blank=True, null=True, verbose_name="commentaire")),
                ("notified_at", models.DateTimeField(blank=True, null=True, verbose_name="notifiée le")),
                ("reminder_sent_at", models.DateTimeField(blank=True, null=True, verbose_name="rappel envoyé le")),
            ],
            options={
                "verbose_name": "entreprise contrôlée",
                "verbose_name_plural": "entreprises contrôlées",
                "unique_together": {("evaluation_campaign", "siae")},
            },
        ),
        migrations.CreateModel(
            name="EvaluatedJobApplication",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "labor_inspector_explanation",
                    models.TextField(blank=True, verbose_name="commentaires de l'inspecteur du travail"),
                ),
                (
                    "evaluated_siae",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_job_applications",
                        to="siae_evaluations.evaluatedsiae",
                        verbose_name="SIAE évaluée",
                    ),
                ),
                (
                    "job_application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_job_applications",
                        to="job_applications.jobapplication",
                        verbose_name="candidature",
                    ),
                ),
            ],
            options={"verbose_name": "auto-prescription"},
        ),
        migrations.CreateModel(
            name="EvaluatedAdministrativeCriteria",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("proof_url", models.URLField(blank=True, max_length=500, verbose_name="lien vers le justificatif")),
                ("uploaded_at", models.DateTimeField(blank=True, null=True, verbose_name="téléversé le")),
                (
                    "administrative_criteria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_administrative_criteria",
                        to="eligibility.administrativecriteria",
                        verbose_name="critère administratif",
                    ),
                ),
                (
                    "evaluated_job_application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evaluated_administrative_criteria",
                        to="siae_evaluations.evaluatedjobapplication",
                        verbose_name="candidature évaluée",
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True, verbose_name="transmis le")),
                (
                    "review_state",
                    models.CharField(
                        choices=[
                            ("PENDING", "En attente"),
                            ("ACCEPTED", "Validé"),
                            ("REFUSED", "Problème constaté"),
                            ("REFUSED_2", "Problème constaté (x2)"),
                        ],
                        default="PENDING",
                        max_length=10,
                        verbose_name="vérification",
                    ),
                ),
            ],
            options={
                "verbose_name": "critère administratif",
                "verbose_name_plural": "critères administratifs",
                "unique_together": {("administrative_criteria", "evaluated_job_application")},
                "ordering": ["evaluated_job_application", "administrative_criteria"],
            },
        ),
    ]
