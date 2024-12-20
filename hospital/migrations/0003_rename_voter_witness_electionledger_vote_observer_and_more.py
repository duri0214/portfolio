# Generated by Django 5.1 on 2024-11-03 12:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospital", "0002_remove_electionledger_vote_status_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="electionledger",
            old_name="voter_witness",
            new_name="vote_observer",
        ),
        migrations.AlterField(
            model_name="electionledger",
            name="election",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="hospital.election",
                verbose_name="選挙名",
            ),
        ),
        migrations.AlterField(
            model_name="electionledger",
            name="remark",
            field=models.CharField(
                blank=True, max_length=255, null=True, verbose_name="備考"
            ),
        ),
    ]
