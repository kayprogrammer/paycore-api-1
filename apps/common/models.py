import uuid
from django.db import models
from .managers import GetOrNoneManager


class BaseModel(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, primary_key=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = GetOrNoneManager()

    class Meta:
        abstract = True
