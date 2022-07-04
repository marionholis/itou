# Generated by Django 4.0.4 on 2022-07-04 17:30

import uuid

from django.db import migrations


def gen_uuid(apps, _):
    Institution = apps.get_model("institutions", "institution")
    for row in Institution.objects.all():
        row.uid = uuid.uuid4()
        row.save(update_fields=["uid"])


class Migration(migrations.Migration):

    dependencies = [
        ("institutions", "0004_institution_uid"),
    ]

    operations = [
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
    ]
