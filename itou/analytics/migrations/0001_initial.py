# Generated by Django 5.0.3 on 2024-03-21 08:45

import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Datum",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                (
                    "code",
                    models.TextField(
                        choices=[
                            ("ER-001", "FS totales"),
                            ("ER-002", "FS (probablement) supprimées"),
                            ("ER-101", "FS intégrées (0000) au premier retour"),
                            ("ER-102", "FS avec une erreur au premier retour"),
                            ("ER-102-3436", "FS avec une erreur 3436 au premier retour"),
                            ("ER-103", "FS ayant eu au moins un retour en erreur"),
                            ("AP-001", "PASS IAE total"),
                            ("AP-002", "PASS IAE annulés"),
                            ("AP-101", "PASS IAE synchronisés avec succès avec pole emploi"),
                            ("AP-102", "PASS IAE en attente de synchronisation avec pole emploi"),
                            ("AP-103", "PASS IAE en erreur de synchronisation avec pole emploi"),
                            ("AP-104", "PASS IAE prêts à être synchronisés avec pole emploi"),
                            ("US-001", "Nombre d'utilisateurs"),
                            ("US-011", "Nombre de demandeurs d'emploi"),
                            ("US-012", "Nombre de prescripteurs"),
                            ("US-013", "Nombre d'employeurs"),
                            ("US-014", "Nombre d'inspecteurs du travail"),
                            ("US-015", "Nombre d'administrateurs"),
                        ]
                    ),
                ),
                ("bucket", models.TextField()),
                ("value", models.IntegerField()),
                ("measured_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "verbose_name_plural": "data",
                "indexes": [models.Index(fields=["measured_at", "code"], name="analytics_d_measure_a59c08_idx")],
                "unique_together": {("code", "bucket")},
            },
        ),
        migrations.CreateModel(
            name="StatsDashboardVisit",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dashboard_id", models.IntegerField(verbose_name="ID tableau de bord Metabase")),
                ("dashboard_name", models.TextField(verbose_name="nom de la vue du tableau de bord")),
                (
                    "department",
                    models.CharField(
                        choices=[
                            ("01", "01 - Ain"),
                            ("02", "02 - Aisne"),
                            ("03", "03 - Allier"),
                            ("04", "04 - Alpes-de-Haute-Provence"),
                            ("05", "05 - Hautes-Alpes"),
                            ("06", "06 - Alpes-Maritimes"),
                            ("07", "07 - Ardèche"),
                            ("08", "08 - Ardennes"),
                            ("09", "09 - Ariège"),
                            ("10", "10 - Aube"),
                            ("11", "11 - Aude"),
                            ("12", "12 - Aveyron"),
                            ("13", "13 - Bouches-du-Rhône"),
                            ("14", "14 - Calvados"),
                            ("15", "15 - Cantal"),
                            ("16", "16 - Charente"),
                            ("17", "17 - Charente-Maritime"),
                            ("18", "18 - Cher"),
                            ("19", "19 - Corrèze"),
                            ("2A", "2A - Corse-du-Sud"),
                            ("2B", "2B - Haute-Corse"),
                            ("21", "21 - Côte-d'Or"),
                            ("22", "22 - Côtes-d'Armor"),
                            ("23", "23 - Creuse"),
                            ("24", "24 - Dordogne"),
                            ("25", "25 - Doubs"),
                            ("26", "26 - Drôme"),
                            ("27", "27 - Eure"),
                            ("28", "28 - Eure-et-Loir"),
                            ("29", "29 - Finistère"),
                            ("30", "30 - Gard"),
                            ("31", "31 - Haute-Garonne"),
                            ("32", "32 - Gers"),
                            ("33", "33 - Gironde"),
                            ("34", "34 - Hérault"),
                            ("35", "35 - Ille-et-Vilaine"),
                            ("36", "36 - Indre"),
                            ("37", "37 - Indre-et-Loire"),
                            ("38", "38 - Isère"),
                            ("39", "39 - Jura"),
                            ("40", "40 - Landes"),
                            ("41", "41 - Loir-et-Cher"),
                            ("42", "42 - Loire"),
                            ("43", "43 - Haute-Loire"),
                            ("44", "44 - Loire-Atlantique"),
                            ("45", "45 - Loiret"),
                            ("46", "46 - Lot"),
                            ("47", "47 - Lot-et-Garonne"),
                            ("48", "48 - Lozère"),
                            ("49", "49 - Maine-et-Loire"),
                            ("50", "50 - Manche"),
                            ("51", "51 - Marne"),
                            ("52", "52 - Haute-Marne"),
                            ("53", "53 - Mayenne"),
                            ("54", "54 - Meurthe-et-Moselle"),
                            ("55", "55 - Meuse"),
                            ("56", "56 - Morbihan"),
                            ("57", "57 - Moselle"),
                            ("58", "58 - Nièvre"),
                            ("59", "59 - Nord"),
                            ("60", "60 - Oise"),
                            ("61", "61 - Orne"),
                            ("62", "62 - Pas-de-Calais"),
                            ("63", "63 - Puy-de-Dôme"),
                            ("64", "64 - Pyrénées-Atlantiques"),
                            ("65", "65 - Hautes-Pyrénées"),
                            ("66", "66 - Pyrénées-Orientales"),
                            ("67", "67 - Bas-Rhin"),
                            ("68", "68 - Haut-Rhin"),
                            ("69", "69 - Rhône"),
                            ("70", "70 - Haute-Saône"),
                            ("71", "71 - Saône-et-Loire"),
                            ("72", "72 - Sarthe"),
                            ("73", "73 - Savoie"),
                            ("74", "74 - Haute-Savoie"),
                            ("75", "75 - Paris"),
                            ("76", "76 - Seine-Maritime"),
                            ("77", "77 - Seine-et-Marne"),
                            ("78", "78 - Yvelines"),
                            ("79", "79 - Deux-Sèvres"),
                            ("80", "80 - Somme"),
                            ("81", "81 - Tarn"),
                            ("82", "82 - Tarn-et-Garonne"),
                            ("83", "83 - Var"),
                            ("84", "84 - Vaucluse"),
                            ("85", "85 - Vendée"),
                            ("86", "86 - Vienne"),
                            ("87", "87 - Haute-Vienne"),
                            ("88", "88 - Vosges"),
                            ("89", "89 - Yonne"),
                            ("90", "90 - Territoire de Belfort"),
                            ("91", "91 - Essonne"),
                            ("92", "92 - Hauts-de-Seine"),
                            ("93", "93 - Seine-Saint-Denis"),
                            ("94", "94 - Val-de-Marne"),
                            ("95", "95 - Val-d'Oise"),
                            ("971", "971 - Guadeloupe"),
                            ("972", "972 - Martinique"),
                            ("973", "973 - Guyane"),
                            ("974", "974 - La Réunion"),
                            ("975", "975 - Saint-Pierre-et-Miquelon"),
                            ("976", "976 - Mayotte"),
                            ("977", "977 - Saint-Barthélémy"),
                            ("978", "978 - Saint-Martin"),
                            ("986", "986 - Wallis-et-Futuna"),
                            ("987", "987 - Polynésie française"),
                            ("988", "988 - Nouvelle-Calédonie"),
                        ],
                        max_length=3,
                        null=True,
                        verbose_name="département",
                    ),
                ),
                ("region", models.TextField(null=True, verbose_name="région")),
                ("current_company_id", models.IntegerField(null=True, verbose_name="ID entreprise courante")),
                (
                    "current_prescriber_organization_id",
                    models.IntegerField(null=True, verbose_name="ID organisation prescriptrice courante"),
                ),
                ("current_institution_id", models.IntegerField(null=True, verbose_name="ID institution courante")),
                (
                    "user_kind",
                    models.TextField(
                        choices=[
                            ("job_seeker", "candidat"),
                            ("prescriber", "prescripteur"),
                            ("employer", "employeur"),
                            ("labor_inspector", "inspecteur du travail"),
                            ("itou_staff", "administrateur"),
                        ],
                        verbose_name="type d'utilisateur",
                    ),
                ),
                ("user_id", models.IntegerField(verbose_name="ID utilisateur")),
                ("measured_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "verbose_name_plural": "visite de tableau de bord",
            },
        ),
    ]
