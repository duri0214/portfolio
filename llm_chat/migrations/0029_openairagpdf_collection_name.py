from django.db import migrations, models


def set_collection_names(apps, schema_editor):
    OpenAIRagPdf = apps.get_model("llm_chat", "OpenAIRagPdf")
    for pdf in OpenAIRagPdf.objects.all():
        pdf.collection_name = f"openai_rag_pdf_{pdf.id}"
        pdf.save(update_fields=["collection_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("llm_chat", "0028_remove_openairagpdf_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="openairagpdf",
            name="collection_name",
            field=models.CharField(
                blank=True,
                max_length=63,
                null=True,
                verbose_name="物理collection名",
            ),
        ),
        migrations.RunPython(set_collection_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="openairagpdf",
            name="collection_name",
            field=models.CharField(
                blank=True,
                max_length=63,
                null=True,
                unique=True,
                verbose_name="物理collection名",
            ),
        ),
    ]
