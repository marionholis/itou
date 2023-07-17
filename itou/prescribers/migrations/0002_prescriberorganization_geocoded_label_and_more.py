# Generated by Django 4.1.8 on 2023-04-26 15:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prescribers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prescriberorganization",
            name="ban_api_resolved_address",
            field=models.TextField(
                blank=True, null=True, verbose_name="Libellé d'adresse retourné par le dernier geocoding"
            ),
        ),
        migrations.AddField(
            model_name="prescriberorganization",
            name="geocoding_updated_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Dernière modification du geocoding"),
        ),
    ]
