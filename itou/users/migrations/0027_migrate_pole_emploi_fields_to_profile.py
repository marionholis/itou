# Generated by Django 4.2.8 on 2023-12-13 15:50
import time

from django.db import migrations
from django.db.models import F, Q


def _migrate_pole_emploi_fields(apps, schema_editor):
    JobSeekerProfile = apps.get_model("users", "JobSeekerProfile")

    profiles_to_migrate = JobSeekerProfile.objects.filter(
        ~Q(pole_emploi_id=F("user__pole_emploi_id"))
        | ~Q(lack_of_pole_emploi_id_reason=F("user__lack_of_pole_emploi_id_reason"))
    ).select_related("user")

    users_nb = 0
    start = time.perf_counter()
    while batch_profiles := profiles_to_migrate[:1000]:
        profiles = []
        for profile in batch_profiles:
            profile.pole_emploi_id = profile.user.pole_emploi_id
            profile.lack_of_pole_emploi_id_reason = profile.user.lack_of_pole_emploi_id_reason
            profiles.append(profile)
        users_nb += JobSeekerProfile.objects.bulk_update(profiles, ("pole_emploi_id", "lack_of_pole_emploi_id_reason"))
        print(f"{users_nb} profiles migrated in {time.perf_counter() - start:.2f} sec")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("users", "0026_jobseekerprofile_lack_of_pole_emploi_id_reason_and_more"),
    ]

    operations = [
        migrations.RunPython(_migrate_pole_emploi_fields, migrations.RunPython.noop, elidable=True),
    ]
