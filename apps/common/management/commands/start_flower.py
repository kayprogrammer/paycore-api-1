"""
Django management command to start Flower monitoring
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config
import subprocess, sys, os


class Command(BaseCommand):
    help = "Start Flower monitoring for Celery"

    def add_arguments(self, parser):
        parser.add_argument(
            "--port",
            type=int,
            default=5555,
            help="Port to run Flower on (default: 5555)",
        )
        parser.add_argument(
            "--address",
            type=str,
            default="0.0.0.0",
            help="Address to bind Flower to (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--basic-auth",
            type=str,
            help="Basic authentication (format: username:password)",
        )
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    def handle(self, *args, **options):
        port = options["port"]
        address = options["address"]
        basic_auth = options["basic_auth"]
        debug = options["debug"]

        # Build Flower command
        cmd = [
            "celery",
            "-A",
            "paycore",
            "flower",
            f"--port={port}",
            f"--address={address}",
        ]

        # Add basic auth if provided
        if basic_auth:
            cmd.append(f"--basic-auth={basic_auth}")

        # Add debug mode
        if debug:
            cmd.append("--debug")

        # Set broker URL
        cmd.extend(["--broker", settings.CELERY_BROKER_URL])

        # Add environment variables
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = config("DJANGO_SETTINGS_MODULE")

        self.stdout.write(
            self.style.SUCCESS(f"Starting Flower on http://{address}:{port}")
        )

        if basic_auth:
            self.stdout.write(f'Basic auth enabled: {basic_auth.split(":")[0]}')

        try:
            # Run Flower
            subprocess.run(cmd, env=env, check=True)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Flower: {e}"))
            sys.exit(1)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Flower shutdown requested"))
