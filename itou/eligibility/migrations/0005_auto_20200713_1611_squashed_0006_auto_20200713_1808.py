# Generated by Django 3.0.4 on 2020-07-13 16:12

from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [('eligibility', '0005_auto_20200713_1611'), ('eligibility', '0006_auto_20200713_1808')]

    dependencies = [
        ('eligibility', '0004_auto_20200331_1702'),
    ]

    operations = [
        migrations.AddField(
            model_name='selectedadministrativecriteria',
            name='data_source',
            field=models.CharField(choices=[('app', 'Application'), ('peconnect', 'APIs PE Connect')], default='app', max_length=20, verbose_name='Source de données'),
        ),
        migrations.AddField(
            model_name='selectedadministrativecriteria',
            name='data_source_updated_at',
            field=models.DateTimeField(null=True, verbose_name='Date de MAJ de la source de données'),
        ),
    ]
