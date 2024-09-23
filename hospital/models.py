from django.db import models


class WardType(models.Model):
    name = models.CharField(verbose_name="病棟種", max_length=100, unique=True)


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


class City(models.Model):
    name = models.CharField(verbose_name="エリア", max_length=100, unique=True)


class CitySector(models.Model):
    name = models.CharField(verbose_name="市区", max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class Election(models.Model):
    name = models.CharField(verbose_name="選挙名", max_length=255, unique=True)
    execution_date = models.DateField(verbose_name="執行日")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
