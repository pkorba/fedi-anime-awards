import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the configured superuser if it does not already exist."

    def handle(self, *args, **options):
        user = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        if not username:
            raise CommandError("Set DJANGO_SUPERUSER_USERNAME.")

        if user.objects.filter(**{user.USERNAME_FIELD: username}).exists():
            self.stdout.write("Configured superuser already exists; skipping.")
            return

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            raise CommandError("Set DJANGO_SUPERUSER_PASSWORD.")

        user.objects.create_superuser(
            username=username,
            password=password,
        )
        self.stdout.write("Configured superuser created.")
