# Generated by Django 4.0.2 on 2022-03-10 21:46

from django.db import migrations, models


def migrate_data_forward(apps, _schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(external_data_source_history__email__source="franceconnect").update(
        identity_provider=User.IdentityProvider.FRANCE_CONNECT
    )


def migrate_data_backward(apps, _schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(external_data_source_history__email__provider="franceconnect").update(identity_provider="")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0037_rename_provider_json_user_external_data_source_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="identity_provider",
            field=models.CharField(
                blank=True,
                choices=[("FC", "FranceConnect")],
                default="",
                max_length=2,
                verbose_name="Fournisseur d'identité (SSO)",
            ),
        ),
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
    ]
