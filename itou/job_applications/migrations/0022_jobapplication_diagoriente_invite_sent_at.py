# Generated by Django 4.2.8 on 2023-12-11 08:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("job_applications", "0021_rename_hidden_for_siae_jobapplication_hidden_for_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobapplication",
            name="diagoriente_invite_sent_at",
            field=models.DateTimeField(
                editable=False, null=True, verbose_name="date d'envoi de l'invitation à utiliser Diagoriente"
            ),
        ),
    ]
