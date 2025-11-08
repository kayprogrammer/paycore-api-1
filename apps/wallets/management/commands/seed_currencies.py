from django.core.management.base import BaseCommand
from django.db import transaction
from apps.wallets.models import Currency
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed currencies using bulk operations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding currencies..."))

        with transaction.atomic():
            # Prepare all currencies data
            currencies_data = self._get_currencies_data()

            # Bulk create/update currencies
            self._bulk_upsert_currencies(currencies_data)

        # Summary
        currency_count = Currency.objects.count()
        active_count = Currency.objects.filter(is_active=True).count()
        crypto_count = Currency.objects.filter(is_crypto=True).count()

        self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully seeded currencies!"))
        self.stdout.write(self.style.SUCCESS(f"   Total Currencies: {currency_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Active: {active_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Cryptocurrencies: {crypto_count}"))
        self.stdout.write(
            self.style.WARNING(
                f"\n⚠️  Note: Exchange rates are approximate. Update them regularly via API."
            )
        )

    def _get_currencies_data(self):
        """Get all currencies data as a list of dictionaries"""
        return [
            # ============ FIAT CURRENCIES (African) ============
            {
                "code": "NGN",
                "name": "Nigerian Naira",
                "symbol": "₦",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("1650.00"),  # 1 USD = 1650 NGN (approx)
            },
            {
                "code": "KES",
                "name": "Kenyan Shilling",
                "symbol": "KSh",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("150.00"),  # 1 USD = 150 KES (approx)
            },
            {
                "code": "GHS",
                "name": "Ghanaian Cedi",
                "symbol": "GH₵",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("15.00"),  # 1 USD = 15 GHS (approx)
            },
            {
                "code": "ZAR",
                "name": "South African Rand",
                "symbol": "R",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("18.50"),  # 1 USD = 18.5 ZAR (approx)
            },
            {
                "code": "EGP",
                "name": "Egyptian Pound",
                "symbol": "E£",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("49.00"),  # 1 USD = 49 EGP (approx)
            },
            # ============ FIAT CURRENCIES (Major) ============
            {
                "code": "USD",
                "name": "US Dollar",
                "symbol": "$",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("1.00"),  # Base currency
            },
            {
                "code": "EUR",
                "name": "Euro",
                "symbol": "€",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("0.92"),  # 1 USD = 0.92 EUR (approx)
            },
            {
                "code": "GBP",
                "name": "British Pound",
                "symbol": "£",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("0.79"),  # 1 USD = 0.79 GBP (approx)
            },
            {
                "code": "CAD",
                "name": "Canadian Dollar",
                "symbol": "C$",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("1.36"),  # 1 USD = 1.36 CAD (approx)
            },
            {
                "code": "AUD",
                "name": "Australian Dollar",
                "symbol": "A$",
                "decimal_places": 2,
                "is_crypto": False,
                "is_active": True,
                "exchange_rate_usd": Decimal("1.52"),  # 1 USD = 1.52 AUD (approx)
            },
            # ============ CRYPTOCURRENCIES ============
            {
                "code": "BTC",
                "name": "Bitcoin",
                "symbol": "₿",
                "decimal_places": 8,
                "is_crypto": True,
                "is_active": True,
                "exchange_rate_usd": Decimal(
                    "0.000023"
                ),  # 1 USD ≈ 0.000023 BTC (approx)
            },
            {
                "code": "ETH",
                "name": "Ethereum",
                "symbol": "Ξ",
                "decimal_places": 8,
                "is_crypto": True,
                "is_active": True,
                "exchange_rate_usd": Decimal("0.00038"),  # 1 USD ≈ 0.00038 ETH (approx)
            },
            {
                "code": "USDT",
                "name": "Tether",
                "symbol": "₮",
                "decimal_places": 6,
                "is_crypto": True,
                "is_active": True,
                "exchange_rate_usd": Decimal("1.00"),  # Stablecoin pegged to USD
            },
            {
                "code": "USDC",
                "name": "USD Coin",
                "symbol": "USDC",
                "decimal_places": 6,
                "is_crypto": True,
                "is_active": True,
                "exchange_rate_usd": Decimal("1.00"),  # Stablecoin pegged to USD
            },
            {
                "code": "BNB",
                "name": "Binance Coin",
                "symbol": "BNB",
                "decimal_places": 8,
                "is_crypto": True,
                "is_active": True,
                "exchange_rate_usd": Decimal("0.0025"),  # 1 USD ≈ 0.0025 BNB (approx)
            },
        ]

    def _bulk_upsert_currencies(self, currencies_data):
        """Bulk create or update currencies using Django's upsert functionality"""
        # Create Currency objects from data
        currencies = [Currency(**data) for data in currencies_data]

        # Perform bulk upsert (create or update on conflict)
        Currency.objects.bulk_create(
            currencies,
            update_conflicts=True,
            unique_fields=["code"],  # The field that determines uniqueness
            update_fields=[  # Fields to update on conflict
                "name",
                "symbol",
                "decimal_places",
                "is_crypto",
                "is_active",
                "exchange_rate_usd",
            ],
        )

        # Display results
        for data in currencies_data:
            crypto_indicator = "🪙" if data["is_crypto"] else "💵"
            self.stdout.write(
                f"✓ Upserted: {crypto_indicator} {data['name']} ({data['code']})"
            )
