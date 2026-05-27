from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("soil_analysis", "0007_rename_land_score_chemical"),
    ]

    operations = [
        migrations.CreateModel(
            name="SoilChemicalMeasurementImportErrors",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("row_number", models.IntegerField(null=True)),
                ("land_name", models.CharField(max_length=256, null=True)),
                ("message", models.TextField()),
                ("remark", models.TextField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(null=True)),
            ],
        ),
    ]
