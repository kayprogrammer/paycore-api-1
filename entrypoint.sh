#!/bin/sh
set -e

# Check which process group we're running
if [ "$FLY_PROCESS_GROUP" = "celery" ]; then
  echo "Starting Celery Worker..."
  exec celery -A paycore worker --loglevel=info --concurrency=2 --max-tasks-per-child=100 --prefetch-multiplier=4
else
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

  echo "Starting Uvicorn with WebSocket support..."
  exec uvicorn paycore.asgi:application --host 0.0.0.0 --port 8000 --workers 2 --ws wsproto --timeout-keep-alive 120
fi
