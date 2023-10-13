# Generated by Django 4.2.6 on 2023-10-13 07:45

from django.db import migrations, models


def rename_siae_staff(apps, schema_editor):
    CancelledApproval = apps.get_model("approvals", "CancelledApproval")
    CancelledApproval.objects.filter(sender_kind="siae_staff").update(sender_kind="employer")


def revert_rename(apps, schema_editor):
    CancelledApproval = apps.get_model("approvals", "CancelledApproval")
    CancelledApproval.objects.filter(sender_kind="employer").update(sender_kind="siae_staff")


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0017_cancelledapproval"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cancelledapproval",
            name="sender_kind",
            field=models.CharField(
                choices=[
                    ("job_seeker", "Demandeur d'emploi"),
                    ("prescriber", "Prescripteur"),
                    ("employer", "Employeur (SIAE)"),
                ],
                verbose_name="origine de la candidature",
            ),
        ),
        migrations.RunPython(rename_siae_staff, reverse_code=revert_rename),
    ]
