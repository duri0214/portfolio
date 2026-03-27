from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("soil_analysis", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
                (
                    "role",
                    models.CharField(choices=[("owner", "圃場オーナー"), ("staff", "採土スタッフ")], max_length=20, verbose_name="ロール"),
                ),
                ("address", models.TextField(blank=True, null=True, verbose_name="住所")),
                (
                    "organization",
                    models.CharField(
                        blank=True, max_length=255, null=True, verbose_name="所属"
                    ),
                ),
                (
                    "area",
                    models.CharField(
                        blank=True, max_length=255, null=True, verbose_name="担当エリア"
                    ),
                ),
                ("remark", models.TextField(blank=True, null=True, verbose_name="備考")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="soil_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ユーザ",
                    ),
                ),
            ],
        ),
    ]
