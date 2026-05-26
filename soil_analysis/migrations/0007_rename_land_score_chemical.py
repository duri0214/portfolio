from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("soil_analysis", "0006_alter_landscorechemical_updated_at"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="LandScoreChemical",
            new_name="SoilChemicalMeasurement",
        ),
    ]
