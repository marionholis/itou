# Generated by Django 4.1.9 on 2023-06-20 16:00

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("siaes", "0003_alter_siae_updated_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="siaejobdescription",
            name="field_history",
            field=models.JSONField(
                default=list,
                encoder=django.core.serializers.json.DjangoJSONEncoder,
                null=True,
                verbose_name="Historique des champs modifiés sur le modèle",
            ),
        ),
    ]
