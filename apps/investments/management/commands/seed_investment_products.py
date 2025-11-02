from django.core.management.base import BaseCommand
from django.db import transaction
from apps.investments.models import (
    InvestmentProduct,
    InvestmentType,
    RiskLevel,
    InterestPayoutFrequency,
)
from apps.wallets.models import Currency
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed investment products using bulk operations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding investment products..."))

        with transaction.atomic():
            # Get currencies
            currencies = self._get_currencies()
            if not currencies:
                self.stdout.write(
                    self.style.ERROR(
                        "❌ No currencies found. Please seed currencies first."
                    )
                )
                return

            # Prepare investment products data
            products_data = self._get_investment_products_data(currencies)

            # Bulk upsert investment products
            self._bulk_upsert_investment_products(products_data)

        # Summary
        product_count = InvestmentProduct.objects.count()
        active_count = InvestmentProduct.objects.filter(is_active=True).count()

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Successfully seeded investment products!")
        )
        self.stdout.write(self.style.SUCCESS(f"   Total Products: {product_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Active Products: {active_count}"))
        self.stdout.write(
            self.style.WARNING(
                f"\n⚠️  Note: Adjust interest rates and terms based on your business requirements."
            )
        )

    def _get_currencies(self):
        """Get available currencies as dict {code: currency_object}"""
        return {c.code: c for c in Currency.objects.all()}

    def _get_investment_products_data(self, currencies):
        """Get all investment products data"""
        products = []

        # ============ FIXED DEPOSITS ============
        for currency_code in ["NGN", "USD", "GHS", "KES"]:
            if currency_code in currencies:
                currency_amounts = {
                    "NGN": (
                        Decimal("10000"),
                        Decimal("50000000"),
                        Decimal("8.50"),
                        Decimal("12.00"),
                    ),
                    "USD": (
                        Decimal("100"),
                        Decimal("100000"),
                        Decimal("6.00"),
                        Decimal("9.00"),
                    ),
                    "GHS": (
                        Decimal("500"),
                        Decimal("500000"),
                        Decimal("10.00"),
                        Decimal("14.00"),
                    ),
                    "KES": (
                        Decimal("5000"),
                        Decimal("5000000"),
                        Decimal("7.00"),
                        Decimal("11.00"),
                    ),
                }

                min_amt, max_amt, rate_90, rate_365 = currency_amounts[currency_code]

                # 90-Day Fixed Deposit
                products.append(
                    {
                        "name": f"90-Day Fixed Deposit - {currency_code}",
                        "product_type": InvestmentType.FIXED_DEPOSIT,
                        "description": f"Lock your funds for 90 days and earn guaranteed returns. Capital protected with {rate_90}% annual interest.",
                        "currency": currencies[currency_code],
                        "min_amount": min_amt,
                        "max_amount": max_amt,
                        "interest_rate": rate_90,
                        "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                        "min_duration_days": 90,
                        "max_duration_days": 90,
                        "risk_level": RiskLevel.LOW,
                        "is_capital_guaranteed": True,
                        "allows_early_liquidation": True,
                        "early_liquidation_penalty": Decimal("5.00"),
                        "allows_auto_renewal": True,
                        "is_active": True,
                        "available_slots": None,
                        "terms_and_conditions": "• Minimum investment period: 90 days\n• Early liquidation attracts 5% penalty\n• Interest paid at maturity\n• Principal is fully guaranteed\n• Auto-renewal available",
                        "benefits": [
                            "Guaranteed returns",
                            "Capital protection",
                            "No market risk",
                            "Flexible liquidation",
                            "Auto-renewal option",
                        ],
                    }
                )

                # 180-Day Fixed Deposit
                products.append(
                    {
                        "name": f"180-Day Fixed Deposit - {currency_code}",
                        "product_type": InvestmentType.FIXED_DEPOSIT,
                        "description": f"Medium-term fixed deposit with better returns. Earn {rate_90 + Decimal('1.5')}% annual interest with capital protection.",
                        "currency": currencies[currency_code],
                        "min_amount": min_amt * 2,
                        "max_amount": max_amt,
                        "interest_rate": rate_90 + Decimal("1.5"),
                        "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                        "min_duration_days": 180,
                        "max_duration_days": 180,
                        "risk_level": RiskLevel.LOW,
                        "is_capital_guaranteed": True,
                        "allows_early_liquidation": True,
                        "early_liquidation_penalty": Decimal("3.00"),
                        "allows_auto_renewal": True,
                        "is_active": True,
                        "available_slots": None,
                        "terms_and_conditions": "• Minimum investment period: 180 days\n• Early liquidation attracts 3% penalty\n• Interest paid at maturity\n• Principal is fully guaranteed\n• Higher returns than 90-day",
                        "benefits": [
                            "Higher returns",
                            "Capital protection",
                            "Lower penalty",
                            "Quarterly updates",
                            "Auto-renewal option",
                        ],
                    }
                )

                # 365-Day Fixed Deposit
                products.append(
                    {
                        "name": f"1-Year Fixed Deposit - {currency_code}",
                        "product_type": InvestmentType.FIXED_DEPOSIT,
                        "description": f"Annual fixed deposit with premium returns. Earn {rate_365}% annual interest with maximum security.",
                        "currency": currencies[currency_code],
                        "min_amount": min_amt * 5,
                        "max_amount": max_amt,
                        "interest_rate": rate_365,
                        "payout_frequency": InterestPayoutFrequency.QUARTERLY,
                        "min_duration_days": 365,
                        "max_duration_days": 365,
                        "risk_level": RiskLevel.LOW,
                        "is_capital_guaranteed": True,
                        "allows_early_liquidation": True,
                        "early_liquidation_penalty": Decimal("2.00"),
                        "allows_auto_renewal": True,
                        "is_active": True,
                        "available_slots": None,
                        "terms_and_conditions": "• Minimum investment period: 365 days\n• Early liquidation attracts 2% penalty\n• Quarterly interest payments\n• Principal is fully guaranteed\n• Best interest rate",
                        "benefits": [
                            "Premium returns",
                            "Quarterly payouts",
                            "Capital protection",
                            "Lowest penalty",
                            "Predictable income",
                        ],
                    }
                )

        # ============ SAVINGS PLANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Flexible Savings Plan - NGN",
                    "product_type": InvestmentType.SAVINGS_PLAN,
                    "description": "Save at your own pace with flexible withdrawals. Earn competitive interest while maintaining liquidity.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("1000.00"),
                    "max_amount": Decimal("10000000.00"),
                    "interest_rate": Decimal("6.00"),
                    "payout_frequency": InterestPayoutFrequency.MONTHLY,
                    "min_duration_days": 30,
                    "max_duration_days": None,  # Flexible
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• No lock-in period after 30 days\n• Withdraw anytime without penalty\n• Monthly interest credits\n• No maximum duration\n• Add funds anytime",
                    "benefits": [
                        "Maximum flexibility",
                        "No penalties",
                        "Monthly interest",
                        "Unlimited duration",
                        "Add funds anytime",
                    ],
                }
            )

            products.append(
                {
                    "name": "Target Savings Plan - NGN",
                    "product_type": InvestmentType.SAVINGS_PLAN,
                    "description": "Save towards a goal with better interest rates. Perfect for planned expenses like rent, vacation, or big purchases.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("5000.00"),
                    "max_amount": Decimal("50000000.00"),
                    "interest_rate": Decimal("9.00"),
                    "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                    "min_duration_days": 90,
                    "max_duration_days": 730,  # 2 years
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": False,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": False,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• Set your target amount and duration\n• Higher interest than flexible savings\n• No withdrawals until maturity\n• Break at maturity or extend\n• Perfect for goal-based saving",
                    "benefits": [
                        "Goal-oriented savings",
                        "Higher interest",
                        "Disciplined saving",
                        "Capital guaranteed",
                        "Flexible duration",
                    ],
                }
            )

        # ============ TREASURY BILLS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "91-Day Treasury Bill",
                    "product_type": InvestmentType.TREASURY_BILL,
                    "description": "Government-backed short-term investment. Lowest risk with stable returns backed by sovereign guarantee.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("100000.00"),
                    "max_amount": Decimal("100000000.00"),
                    "interest_rate": Decimal("10.00"),
                    "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                    "min_duration_days": 91,
                    "max_duration_days": 91,
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": False,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": 500,  # Limited slots
                    "terms_and_conditions": "• Government-backed security\n• Fixed 91-day tenor\n• No early liquidation\n• Discount pricing model\n• Auto-renewal available",
                    "benefits": [
                        "Government guarantee",
                        "Zero credit risk",
                        "Predictable returns",
                        "Institutional grade",
                        "Tax advantages",
                    ],
                }
            )

            products.append(
                {
                    "name": "182-Day Treasury Bill",
                    "product_type": InvestmentType.TREASURY_BILL,
                    "description": "Medium-term government security with better returns. Ideal for risk-averse investors seeking safety.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("100000.00"),
                    "max_amount": Decimal("100000000.00"),
                    "interest_rate": Decimal("11.00"),
                    "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                    "min_duration_days": 182,
                    "max_duration_days": 182,
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": False,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": 300,
                    "terms_and_conditions": "• Government-backed security\n• Fixed 182-day tenor\n• No early liquidation\n• Better returns than 91-day\n• Auto-renewal available",
                    "benefits": [
                        "Government guarantee",
                        "Higher returns",
                        "Zero credit risk",
                        "Safe haven asset",
                        "Portfolio diversification",
                    ],
                }
            )

            products.append(
                {
                    "name": "364-Day Treasury Bill",
                    "product_type": InvestmentType.TREASURY_BILL,
                    "description": "Long-term treasury bill with maximum returns. Best rates for government-backed securities.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("100000.00"),
                    "max_amount": Decimal("100000000.00"),
                    "interest_rate": Decimal("12.50"),
                    "payout_frequency": InterestPayoutFrequency.AT_MATURITY,
                    "min_duration_days": 364,
                    "max_duration_days": 364,
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": False,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": 200,
                    "terms_and_conditions": "• Government-backed security\n• Fixed 364-day tenor\n• No early liquidation\n• Premium returns\n• Auto-renewal available",
                    "benefits": [
                        "Government guarantee",
                        "Premium returns",
                        "Maximum tenor",
                        "Portfolio anchor",
                        "Flight to safety",
                    ],
                }
            )

        # ============ MONEY MARKET FUNDS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Money Market Fund - Conservative",
                    "product_type": InvestmentType.MONEY_MARKET,
                    "description": "Low-risk money market fund investing in treasury bills, commercial papers, and short-term bonds.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("50000.00"),
                    "max_amount": None,
                    "interest_rate": Decimal("11.50"),
                    "payout_frequency": InterestPayoutFrequency.MONTHLY,
                    "min_duration_days": 30,
                    "max_duration_days": None,  # Flexible
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": False,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• Professionally managed fund\n• Daily liquidity after 30 days\n• No lock-in period\n• Monthly distributions\n• Low volatility",
                    "benefits": [
                        "Professional management",
                        "Daily liquidity",
                        "Diversified portfolio",
                        "Monthly income",
                        "Better than savings",
                    ],
                }
            )

        if "USD" in currencies:
            products.append(
                {
                    "name": "Money Market Fund - USD",
                    "product_type": InvestmentType.MONEY_MARKET,
                    "description": "USD-denominated money market fund for currency diversification and stable dollar returns.",
                    "currency": currencies["USD"],
                    "min_amount": Decimal("500.00"),
                    "max_amount": None,
                    "interest_rate": Decimal("5.50"),
                    "payout_frequency": InterestPayoutFrequency.QUARTERLY,
                    "min_duration_days": 90,
                    "max_duration_days": None,
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": False,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("0.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• USD-denominated fund\n• Quarterly distributions\n• 90-day minimum holding\n• Currency hedge\n• Globally diversified",
                    "benefits": [
                        "Dollar exposure",
                        "Currency hedging",
                        "Global diversification",
                        "Stable returns",
                        "Quarterly income",
                    ],
                }
            )

        # ============ BONDS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Corporate Bond Fund - High Grade",
                    "product_type": InvestmentType.BOND,
                    "description": "Invest in high-grade corporate bonds from blue-chip companies. Higher returns than treasury with managed risk.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("250000.00"),
                    "max_amount": Decimal("50000000.00"),
                    "interest_rate": Decimal("14.00"),
                    "payout_frequency": InterestPayoutFrequency.SEMI_ANNUALLY,
                    "min_duration_days": 365,
                    "max_duration_days": 1825,  # 5 years
                    "risk_level": RiskLevel.MEDIUM,
                    "is_capital_guaranteed": False,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("5.00"),
                    "allows_auto_renewal": False,
                    "is_active": True,
                    "available_slots": 100,
                    "terms_and_conditions": "• Investment grade bonds only\n• Semi-annual coupon payments\n• 1-5 year maturity range\n• Early exit available with penalty\n• Professional credit analysis",
                    "benefits": [
                        "Higher yields",
                        "Regular income",
                        "Investment grade",
                        "Professional selection",
                        "Semi-annual coupons",
                    ],
                }
            )

            products.append(
                {
                    "name": "Government Bond Fund",
                    "product_type": InvestmentType.BOND,
                    "description": "Long-term government bonds with stable returns. Perfect for retirement planning and long-term wealth building.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("100000.00"),
                    "max_amount": Decimal("100000000.00"),
                    "interest_rate": Decimal("13.50"),
                    "payout_frequency": InterestPayoutFrequency.SEMI_ANNUALLY,
                    "min_duration_days": 730,
                    "max_duration_days": 7300,  # 20 years
                    "risk_level": RiskLevel.LOW,
                    "is_capital_guaranteed": True,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("3.00"),
                    "allows_auto_renewal": False,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• Federal government guarantee\n• Semi-annual interest payments\n• 2-20 year maturity options\n• Secondary market liquidity\n• Tax advantages",
                    "benefits": [
                        "Government backed",
                        "Long-term security",
                        "Regular income",
                        "Tax efficient",
                        "Estate planning",
                    ],
                }
            )

        # ============ MUTUAL FUNDS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Balanced Mutual Fund",
                    "product_type": InvestmentType.MUTUAL_FUND,
                    "description": "Diversified portfolio of stocks and bonds. Balanced risk-return profile for moderate investors.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("25000.00"),
                    "max_amount": None,
                    "interest_rate": Decimal("15.00"),  # Expected annual return
                    "payout_frequency": InterestPayoutFrequency.QUARTERLY,
                    "min_duration_days": 180,
                    "max_duration_days": None,
                    "risk_level": RiskLevel.MEDIUM,
                    "is_capital_guaranteed": False,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("1.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• 60% bonds, 40% stocks allocation\n• Professionally managed\n• Quarterly distributions\n• 180-day minimum recommended\n• Historical returns 12-18%",
                    "benefits": [
                        "Diversification",
                        "Professional management",
                        "Growth potential",
                        "Income generation",
                        "Moderate risk",
                    ],
                }
            )

            products.append(
                {
                    "name": "Equity Growth Fund",
                    "product_type": InvestmentType.MUTUAL_FUND,
                    "description": "Aggressive growth fund focused on high-potential stocks. For investors seeking maximum capital appreciation.",
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("50000.00"),
                    "max_amount": None,
                    "interest_rate": Decimal("20.00"),  # Expected annual return
                    "payout_frequency": InterestPayoutFrequency.ANNUALLY,
                    "min_duration_days": 365,
                    "max_duration_days": None,
                    "risk_level": RiskLevel.HIGH,
                    "is_capital_guaranteed": False,
                    "allows_early_liquidation": True,
                    "early_liquidation_penalty": Decimal("2.00"),
                    "allows_auto_renewal": True,
                    "is_active": True,
                    "available_slots": None,
                    "terms_and_conditions": "• 90% equities, 10% cash\n• Focus on growth stocks\n• Annual distributions\n• Minimum 1-year holding recommended\n• Historical returns 15-25%",
                    "benefits": [
                        "High growth potential",
                        "Capital appreciation",
                        "Market exposure",
                        "Professional stock picking",
                        "Long-term wealth",
                    ],
                }
            )

        return products

    def _bulk_upsert_investment_products(self, products_data):
        """Bulk create or update investment products"""
        # Get existing products by (name, currency) combination
        existing_products = {}
        for product in InvestmentProduct.objects.select_related("currency").all():
            key = (product.name, product.currency_id)
            existing_products[key] = product

        products_to_create = []
        products_to_update = []

        for data in products_data:
            currency_id = data["currency"].id
            name = data["name"]
            key = (name, currency_id)

            if key in existing_products:
                # Update existing product
                existing_product = existing_products[key]
                for field, value in data.items():
                    setattr(existing_product, field, value)
                products_to_update.append(existing_product)
                self.stdout.write(f"↻ Updated: {name}")
            else:
                # Prepare for bulk creation
                products_to_create.append(InvestmentProduct(**data))

        # Bulk update existing products
        if products_to_update:
            InvestmentProduct.objects.bulk_update(
                products_to_update,
                [
                    "product_type",
                    "description",
                    "min_amount",
                    "max_amount",
                    "interest_rate",
                    "payout_frequency",
                    "min_duration_days",
                    "max_duration_days",
                    "risk_level",
                    "is_capital_guaranteed",
                    "allows_early_liquidation",
                    "early_liquidation_penalty",
                    "allows_auto_renewal",
                    "is_active",
                    "available_slots",
                    "terms_and_conditions",
                    "benefits",
                ],
            )

        # Bulk create new products
        if products_to_create:
            created = InvestmentProduct.objects.bulk_create(
                products_to_create, ignore_conflicts=True
            )
            for product in created:
                self.stdout.write(f"✓ Created: {product.name}")
