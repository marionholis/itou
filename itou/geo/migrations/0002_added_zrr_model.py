# Generated by Django 4.1.2 on 2022-11-09 15:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ZRR",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("insee_code", models.CharField(max_length=5, verbose_name="Code INSEE de la commune")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("C", "Classée en ZRR"),
                            ("NC", "Non-classée en ZRR"),
                            ("PC", "Partiellement classée en ZRR"),
                        ],
                        max_length=2,
                        verbose_name="Classement en ZRR",
                    ),
                ),
            ],
            options={
                "verbose_name": "Classification en Zone de Revitalisation Rurale (ZRR)",
                "verbose_name_plural": "Classifications en Zone de Revitalisation Rurale (ZRR)",
            },
        ),
        migrations.AlterField(
            model_name="qpv",
            name="code",
            field=models.CharField(max_length=8, verbose_name="Code"),
        ),
        migrations.AddIndex(
            model_name="zrr",
            index=models.Index(fields=["insee_code"], name="geo_zrr_insee_c_75da81_idx"),
        ),
        migrations.AddIndex(
            model_name="zrr",
            index=models.Index(fields=["status"], name="geo_zrr_status_04ec0b_idx"),
        ),
    ]
