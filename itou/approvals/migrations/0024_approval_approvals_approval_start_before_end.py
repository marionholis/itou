# Generated by Django 4.2.8 on 2023-12-14 09:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0023_cancelledapproval_approvals_cancelledapproval_start_before_end"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="approval",
            constraint=models.CheckConstraint(
                check=models.Q(("start_at__lt", models.F("end_at"))), name="approvals_approval_start_before_end"
            ),
        ),
    ]
