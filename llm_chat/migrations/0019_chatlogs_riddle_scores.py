from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm_chat", "0018_alter_chatlogs_next_riddle_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatlogs",
            name="riddle_scores",
            field=models.JSONField(
                blank=True,
                help_text="なぞなぞの単問評価スコア（correctness, reasoning, creativity, rebuttal）",
                null=True,
            ),
        ),
    ]
