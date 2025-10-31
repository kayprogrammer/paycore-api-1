from django.db import models

from apps.common.models import BaseModel


class Country(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # ISO country code
    currency = models.CharField(max_length=10)  # e.g. USD, EUR
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
