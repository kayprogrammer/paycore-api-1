from django.core.management.base import BaseCommand
from django.db import transaction
from apps.loans.models import LoanProduct, LoanProductType, RepaymentFrequency
from apps.wallets.models import Currency
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed loan products using bulk operations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding loan products..."))

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

            # Prepare loan products data
            products_data = self._get_loan_products_data(currencies)

            # Bulk upsert loan products
            self._bulk_upsert_loan_products(products_data)

        # Summary
        product_count = LoanProduct.objects.count()
        active_count = LoanProduct.objects.filter(is_active=True).count()

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Successfully seeded loan products!")
        )
        self.stdout.write(self.style.SUCCESS(f"   Total Products: {product_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Active Products: {active_count}"))
        self.stdout.write(
            self.style.WARNING(
                f"\n⚠️  Note: Adjust interest rates and eligibility criteria based on your business requirements."
            )
        )

    def _get_currencies(self):
        """Get available currencies as dict {code: currency_object}"""
        return {c.code: c for c in Currency.objects.all()}

    def _get_loan_products_data(self, currencies):
        """Get all loan products data"""
        products = []

        # ============ PAYDAY LOANS (Short-term emergency) ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Quick Cash - Payday Loan",
                    "description": "Short-term loan to cover expenses until your next payday. Fast approval, no collateral required.",
                    "product_type": LoanProductType.PAYDAY,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("5000.00"),
                    "max_amount": Decimal("500000.00"),
                    "min_interest_rate": Decimal("15.00"),
                    "max_interest_rate": Decimal("25.00"),
                    "min_tenure_months": 1,
                    "max_tenure_months": 3,
                    "processing_fee_percentage": Decimal("2.50"),
                    "processing_fee_fixed": Decimal("0.00"),
                    "late_payment_fee": Decimal("1000.00"),
                    "early_repayment_fee_percentage": Decimal("0.00"),
                    "min_credit_score": 500,
                    "requires_collateral": False,
                    "requires_guarantor": False,
                    "min_account_age_days": 30,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.WEEKLY,
                        RepaymentFrequency.BIWEEKLY,
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_income": 30000,
                        "employment_status": ["employed", "self_employed"],
                        "max_active_loans": 2,
                        "description": "Must have regular income and active bank account",
                    },
                }
            )

        # ============ PERSONAL LOANS ============
        for currency_code in ["NGN", "USD", "GHS", "KES"]:
            if currency_code in currencies:
                currency_amounts = {
                    "NGN": (Decimal("50000"), Decimal("5000000")),
                    "USD": (Decimal("100"), Decimal("10000")),
                    "GHS": (Decimal("500"), Decimal("50000")),
                    "KES": (Decimal("5000"), Decimal("500000")),
                }
                min_amt, max_amt = currency_amounts[currency_code]

                products.append(
                    {
                        "name": f"Personal Loan - {currency_code}",
                        "description": "Flexible personal loan for any purpose - home renovation, medical bills, education, or personal expenses.",
                        "product_type": LoanProductType.PERSONAL,
                        "currency": currencies[currency_code],
                        "min_amount": min_amt,
                        "max_amount": max_amt,
                        "min_interest_rate": Decimal("10.00"),
                        "max_interest_rate": Decimal("18.00"),
                        "min_tenure_months": 6,
                        "max_tenure_months": 36,
                        "processing_fee_percentage": Decimal("1.50"),
                        "processing_fee_fixed": Decimal("0.00"),
                        "late_payment_fee": (
                            Decimal("2000.00")
                            if currency_code == "NGN"
                            else Decimal("20.00")
                        ),
                        "early_repayment_fee_percentage": Decimal("1.00"),
                        "min_credit_score": 600,
                        "requires_collateral": False,
                        "requires_guarantor": True,
                        "min_account_age_days": 90,
                        "allowed_repayment_frequencies": [
                            RepaymentFrequency.MONTHLY,
                            RepaymentFrequency.BIWEEKLY,
                        ],
                        "is_active": True,
                        "eligibility_criteria": {
                            "min_monthly_income": (
                                50000 if currency_code == "NGN" else 500
                            ),
                            "employment_status": [
                                "employed",
                                "self_employed",
                                "business_owner",
                            ],
                            "max_active_loans": 3,
                            "min_credit_score": 600,
                            "description": "Requires guarantor and proof of regular income",
                        },
                    }
                )

        # ============ BUSINESS LOANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "SME Business Loan",
                    "description": "Working capital loan for small and medium enterprises. Grow your business with flexible repayment terms.",
                    "product_type": LoanProductType.BUSINESS,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("500000.00"),
                    "max_amount": Decimal("50000000.00"),
                    "min_interest_rate": Decimal("12.00"),
                    "max_interest_rate": Decimal("20.00"),
                    "min_tenure_months": 12,
                    "max_tenure_months": 60,
                    "processing_fee_percentage": Decimal("2.00"),
                    "processing_fee_fixed": Decimal("5000.00"),
                    "late_payment_fee": Decimal("5000.00"),
                    "early_repayment_fee_percentage": Decimal("2.00"),
                    "min_credit_score": 650,
                    "requires_collateral": True,
                    "requires_guarantor": True,
                    "min_account_age_days": 180,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.MONTHLY,
                        RepaymentFrequency.QUARTERLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_revenue": 200000,
                        "business_age_months": 12,
                        "employment_status": ["business_owner", "self_employed"],
                        "max_active_loans": 2,
                        "min_credit_score": 650,
                        "required_documents": [
                            "business_registration",
                            "bank_statements_6_months",
                            "tax_returns",
                        ],
                        "description": "Requires business registration, financial statements, and collateral",
                    },
                }
            )

        if "USD" in currencies:
            products.append(
                {
                    "name": "International Business Loan",
                    "description": "USD-denominated business loan for international trade, import/export, and cross-border business operations.",
                    "product_type": LoanProductType.BUSINESS,
                    "currency": currencies["USD"],
                    "min_amount": Decimal("5000.00"),
                    "max_amount": Decimal("100000.00"),
                    "min_interest_rate": Decimal("8.00"),
                    "max_interest_rate": Decimal("15.00"),
                    "min_tenure_months": 12,
                    "max_tenure_months": 48,
                    "processing_fee_percentage": Decimal("2.50"),
                    "processing_fee_fixed": Decimal("100.00"),
                    "late_payment_fee": Decimal("100.00"),
                    "early_repayment_fee_percentage": Decimal("2.00"),
                    "min_credit_score": 700,
                    "requires_collateral": True,
                    "requires_guarantor": True,
                    "min_account_age_days": 365,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_revenue": 10000,
                        "business_age_months": 24,
                        "employment_status": ["business_owner"],
                        "max_active_loans": 1,
                        "min_credit_score": 700,
                        "required_documents": [
                            "business_registration",
                            "bank_statements_12_months",
                            "audited_financials",
                            "trade_license",
                        ],
                        "description": "Premium business loan for established international businesses",
                    },
                }
            )

        # ============ EMERGENCY LOANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Emergency Instant Loan",
                    "description": "Instant loan for medical emergencies, urgent repairs, or unexpected expenses. Get approved in minutes.",
                    "product_type": LoanProductType.EMERGENCY,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("10000.00"),
                    "max_amount": Decimal("200000.00"),
                    "min_interest_rate": Decimal("18.00"),
                    "max_interest_rate": Decimal("30.00"),
                    "min_tenure_months": 1,
                    "max_tenure_months": 6,
                    "processing_fee_percentage": Decimal("3.00"),
                    "processing_fee_fixed": Decimal("0.00"),
                    "late_payment_fee": Decimal("1500.00"),
                    "early_repayment_fee_percentage": Decimal("0.00"),
                    "min_credit_score": 450,
                    "requires_collateral": False,
                    "requires_guarantor": False,
                    "min_account_age_days": 14,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.WEEKLY,
                        RepaymentFrequency.BIWEEKLY,
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_income": 25000,
                        "employment_status": ["employed", "self_employed"],
                        "max_active_loans": 1,
                        "description": "Quick approval for emergencies. Higher interest due to instant processing.",
                    },
                }
            )

        # ============ EDUCATION LOANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Education/Student Loan",
                    "description": "Finance your education or your child's education. Low interest rates with flexible repayment after graduation.",
                    "product_type": LoanProductType.EDUCATION,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("100000.00"),
                    "max_amount": Decimal("5000000.00"),
                    "min_interest_rate": Decimal("8.00"),
                    "max_interest_rate": Decimal("12.00"),
                    "min_tenure_months": 12,
                    "max_tenure_months": 48,
                    "processing_fee_percentage": Decimal("1.00"),
                    "processing_fee_fixed": Decimal("0.00"),
                    "late_payment_fee": Decimal("2000.00"),
                    "early_repayment_fee_percentage": Decimal("0.00"),
                    "min_credit_score": 550,
                    "requires_collateral": False,
                    "requires_guarantor": True,
                    "min_account_age_days": 60,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "age_min": 18,
                        "age_max": 35,
                        "max_active_loans": 1,
                        "required_documents": [
                            "admission_letter",
                            "school_fees_invoice",
                            "guarantor_employment_letter",
                        ],
                        "description": "For students and parents. Moratorium period available during study.",
                    },
                }
            )

        # ============ AUTO LOANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Auto/Vehicle Loan",
                    "description": "Finance your dream car. Up to 80% of vehicle value with competitive interest rates.",
                    "product_type": LoanProductType.AUTO,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("1000000.00"),
                    "max_amount": Decimal("20000000.00"),
                    "min_interest_rate": Decimal("14.00"),
                    "max_interest_rate": Decimal("22.00"),
                    "min_tenure_months": 12,
                    "max_tenure_months": 60,
                    "processing_fee_percentage": Decimal("1.50"),
                    "processing_fee_fixed": Decimal("10000.00"),
                    "late_payment_fee": Decimal("5000.00"),
                    "early_repayment_fee_percentage": Decimal("2.00"),
                    "min_credit_score": 650,
                    "requires_collateral": True,
                    "requires_guarantor": True,
                    "min_account_age_days": 180,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_income": 150000,
                        "employment_status": [
                            "employed",
                            "self_employed",
                            "business_owner",
                        ],
                        "max_active_loans": 2,
                        "min_credit_score": 650,
                        "max_loan_to_value": 80,  # 80% of vehicle value
                        "required_documents": [
                            "vehicle_proforma_invoice",
                            "drivers_license",
                            "proof_of_insurance",
                            "employment_letter",
                        ],
                        "description": "Vehicle serves as collateral. Comprehensive insurance required.",
                    },
                }
            )

        # ============ HOME LOANS ============
        if "NGN" in currencies:
            products.append(
                {
                    "name": "Home/Mortgage Loan",
                    "description": "Own your dream home with our long-term mortgage loan. Up to 90% financing with competitive rates.",
                    "product_type": LoanProductType.HOME,
                    "currency": currencies["NGN"],
                    "min_amount": Decimal("5000000.00"),
                    "max_amount": Decimal("100000000.00"),
                    "min_interest_rate": Decimal("10.00"),
                    "max_interest_rate": Decimal("16.00"),
                    "min_tenure_months": 60,
                    "max_tenure_months": 300,  # 25 years
                    "processing_fee_percentage": Decimal("1.00"),
                    "processing_fee_fixed": Decimal("50000.00"),
                    "late_payment_fee": Decimal("10000.00"),
                    "early_repayment_fee_percentage": Decimal("3.00"),
                    "min_credit_score": 700,
                    "requires_collateral": True,
                    "requires_guarantor": True,
                    "min_account_age_days": 365,
                    "allowed_repayment_frequencies": [
                        RepaymentFrequency.MONTHLY,
                    ],
                    "is_active": True,
                    "eligibility_criteria": {
                        "min_monthly_income": 300000,
                        "age_min": 25,
                        "age_max": 55,
                        "employment_status": ["employed", "business_owner"],
                        "max_active_loans": 1,
                        "min_credit_score": 700,
                        "max_loan_to_value": 90,  # 90% of property value
                        "required_documents": [
                            "property_valuation",
                            "land_title_documents",
                            "survey_plan",
                            "building_plan_approval",
                            "employment_letter",
                            "bank_statements_12_months",
                            "tax_clearance",
                        ],
                        "description": "Premium mortgage product for property acquisition or construction.",
                    },
                }
            )

        return products

    def _bulk_upsert_loan_products(self, products_data):
        """Bulk create or update loan products"""
        # Get existing products by (name, currency) combination
        existing_products = {}
        for product in LoanProduct.objects.select_related("currency").all():
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
                products_to_create.append(LoanProduct(**data))

        # Bulk update existing products
        if products_to_update:
            LoanProduct.objects.bulk_update(
                products_to_update,
                [
                    "description",
                    "product_type",
                    "min_amount",
                    "max_amount",
                    "min_interest_rate",
                    "max_interest_rate",
                    "min_tenure_months",
                    "max_tenure_months",
                    "processing_fee_percentage",
                    "processing_fee_fixed",
                    "late_payment_fee",
                    "early_repayment_fee_percentage",
                    "min_credit_score",
                    "requires_collateral",
                    "requires_guarantor",
                    "min_account_age_days",
                    "allowed_repayment_frequencies",
                    "is_active",
                    "eligibility_criteria",
                ],
            )

        # Bulk create new products
        if products_to_create:
            created = LoanProduct.objects.bulk_create(
                products_to_create, ignore_conflicts=True
            )
            for product in created:
                self.stdout.write(f"✓ Created: {product.name}")
