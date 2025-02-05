# Generated by Django 4.2.10 on 2024-02-14 14:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0037_really_remove_user_nir_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobseekerprofile",
            name="asp_uid",
            field=models.TextField(
                blank=True,
                help_text="Si vide, une valeur sera assignée automatiquement.",
                max_length=30,
                null=True,
                unique=True,
                verbose_name="ID unique envoyé à l'ASP",
            ),
        ),
    ]
