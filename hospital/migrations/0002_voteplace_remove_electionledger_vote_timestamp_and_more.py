# Generated by Django 5.1 on 2024-09-23 14:20

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospital", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VotePlace",
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
                ("name", models.CharField(max_length=255)),
            ],
        ),
        migrations.RemoveField(
            model_name="electionledger",
            name="vote_timestamp",
        ),
        migrations.AddField(
            model_name="electionledger",
            name="ballot_received_date",
            field=models.DateField(
                blank=True, null=True, verbose_name="投票用紙受領日"
            ),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="billing_method",
            field=models.CharField(
                blank=True,
                choices=[(1, "代理・直接"), (2, "代理・郵便")],
                max_length=5,
                null=True,
                verbose_name="投票用紙請求の方法",
            ),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="delivery_date",
            field=models.DateField(
                blank=True, null=True, verbose_name="投票用紙送付日"
            ),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="proxy_billing_date",
            field=models.DateField(blank=True, null=True, verbose_name="代理請求日"),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="proxy_billing_request_date",
            field=models.DateField(
                blank=True, null=True, verbose_name="代理請求の依頼を受けた日"
            ),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="remark",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="vote_city_sector",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="hospital.citysector",
                verbose_name="投票区",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="electionledger",
            name="vote_date",
            field=models.DateField(blank=True, null=True, verbose_name="投票日"),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="vote_ward",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="hospital.ward",
                verbose_name="病棟",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="electionledger",
            name="voter_witness",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="voter_witness",
                to=settings.AUTH_USER_MODEL,
                verbose_name="投票立会人",
            ),
        ),
        migrations.AddField(
            model_name="electionledger",
            name="whether_to_apply_for_proxy_voting",
            field=models.CharField(
                blank=True,
                choices=[(1, "無"), (2, "有")],
                max_length=1,
                null=True,
                verbose_name="代理投票申請の有無",
            ),
        ),
        migrations.AlterField(
            model_name="electionledger",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="取込日"),
        ),
        migrations.AlterField(
            model_name="electionledger",
            name="vote_status",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="hospital.votestatus",
            ),
        ),
        migrations.AlterField(
            model_name="electionledger",
            name="voter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="voter",
                to=settings.AUTH_USER_MODEL,
                verbose_name="選挙人氏名",
            ),
        ),
        migrations.CreateModel(
            name="UserAttribute",
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
                ("address", models.TextField(verbose_name="住所")),
                ("date_of_birth", models.DateField(verbose_name="生年月日")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="electionledger",
            name="vote_place",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="hospital.voteplace",
                verbose_name="投票場所",
            ),
        ),
    ]