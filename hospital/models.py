from django.db import models


class WardType(models.Model):
    name = models.CharField(verbose_name="病棟種", max_length=100)


class Ward(models.Model):
    abbreviation = models.CharField(verbose_name="略称", unique=True, max_length=10)
    ward_type = models.ForeignKey(
        WardType, verbose_name="病棟種", on_delete=models.CASCADE
    )
    name = models.CharField(
        verbose_name="病棟名", max_length=100, null=False, blank=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
