# Generated by Django 4.2.10 on 2024-02-15 12:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0041_alter_jobseekerprofile_asp_uid"),
    ]

    operations = [
        # This migration can be merged into 0040_remove_user_asp_uid once run in production
        migrations.RunSQL(
            'ALTER TABLE "users_user" DROP COLUMN asp_uid;',
            elidable=True,
        ),
    ]
