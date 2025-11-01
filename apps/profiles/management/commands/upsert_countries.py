"""
Django management command to upsert countries data
"""

from django.core.management.base import BaseCommand
from .countries_data import COUNTRIES_DATA
from apps.profiles.models import Country


class Command(BaseCommand):
    help = "Bulk upsert countries data"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Bulk upserting countries..."))
        countries_to_create = [
            Country(
                name=country["name"],
                code=country["code"],
                currency=country["currency_code"],
            )
            for country in COUNTRIES_DATA
        ]
        Country.objects.bulk_create(
            countries_to_create,
            update_conflicts=True,
            update_fields=["name", "currency"],
            unique_fields=["code"],
        )
        self.stdout.write(self.style.SUCCESS("Countries upserted successfully"))
