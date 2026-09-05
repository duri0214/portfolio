from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("usa_research", "0014_alter_rssfeed_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="mscicountryweightreport",
            name="model_name",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="LLMモデル名",
            ),
        ),
    ]
