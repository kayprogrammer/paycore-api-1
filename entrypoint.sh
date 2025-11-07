#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Seeding users..."
python manage.py seed_users

echo "Upserting countries..."
python manage.py upsert_countries

echo "Seeding currencies..."
python manage.py seed_currencies

echo "Seeding bill providers..."
python manage.py seed_bill_providers

echo "Seeding loan products..."
python manage.py seed_loan_products

echo "Seeding investment products..."
python manage.py seed_investment_products

echo "Seeding FAQs..."
python manage.py seed_faqs

echo "Starting Gunicorn..."
exec gunicorn --bind :8000 --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 120 --max-requests 1000 --max-requests-jitter 100 paycore.asgi:application
