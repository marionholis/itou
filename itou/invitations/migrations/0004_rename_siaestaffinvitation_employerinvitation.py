# Generated by Django 4.2.6 on 2023-10-13 07:53

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0004_siaejobdescription_field_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("invitations", "0003_extend_all_ddets_log_invitations"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="SiaeStaffInvitation",
            new_name="EmployerInvitation",
        ),
    ]
