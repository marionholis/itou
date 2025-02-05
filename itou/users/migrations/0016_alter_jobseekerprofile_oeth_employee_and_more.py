# Generated by Django 4.1.5 on 2023-03-17 10:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_user_user_lack_of_nir_reason_or_nir"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobseekerprofile",
            name="oeth_employee",
            field=models.BooleanField(
                default=False,
                help_text="L'obligation d’emploi des travailleurs handicapés",
                verbose_name="bénéficiaire de la loi handicap (OETH)",
            ),
        ),
        migrations.AlterField(
            model_name="jobseekerprofile",
            name="rqth_employee",
            field=models.BooleanField(
                default=False,
                help_text="Reconnaissance de la qualité de travailleur handicapé",
                verbose_name="titulaire de la RQTH",
            ),
        ),
    ]
