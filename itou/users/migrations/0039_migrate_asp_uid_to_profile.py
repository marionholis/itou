# Generated by Django 4.2.10 on 2024-02-14 14:54
import time

from django.db import migrations
from django.db.models import F


def _migrate_asp_uid(apps, schema_editor):
    JobSeekerProfile = apps.get_model("users", "JobSeekerProfile")

    profiles_to_migrate = (
        JobSeekerProfile.objects.exclude(asp_uid=F("user__asp_uid"))  # Those with identical asp_uid
        .exclude(asp_uid__isnull=True, user__asp_uid__isnull=True)  # Those with identical null asp_uid
        .select_related("user")
    )

    users_nb = 0
    start = time.perf_counter()
    while batch_profiles := profiles_to_migrate[:1000]:
        profiles = []
        for profile in batch_profiles:
            profile.asp_uid = profile.user.asp_uid
            profiles.append(profile)
        users_nb += JobSeekerProfile.objects.bulk_update(profiles, ("asp_uid",))
        print(f"{users_nb} profiles migrated in {time.perf_counter() - start:.2f} sec")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("users", "0038_jobseekerprofile_asp_uid"),
    ]

    operations = [
        migrations.RunPython(_migrate_asp_uid, migrations.RunPython.noop, elidable=True),
    ]
