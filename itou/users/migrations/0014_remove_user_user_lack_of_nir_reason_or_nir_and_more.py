# Generated by Django 4.1.6 on 2023-02-09 20:16

from django.db import migrations, models

import itou.utils.models
import itou.utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_user_has_kind"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="user",
            name="user_lack_of_nir_reason_or_nir",
        ),
        migrations.AlterField(
            model_name="user",
            name="nir",
            field=models.CharField(
                blank=True,
                default="",
                max_length=15,
                validators=[itou.utils.validators.validate_nir],
                verbose_name="NIR",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=itou.utils.models.UniqueConstraintWithErrorCode(
                models.F("nir"),
                condition=models.Q(("nir", ""), _negated=True),
                validation_error_code="unique_nir_if_not_empty",
                name="unique_nir_if_not_empty",
                violation_error_message="Ce numéro de sécurité sociale est déjà associé à un autre utilisateur.",
            ),
        ),
    ]
