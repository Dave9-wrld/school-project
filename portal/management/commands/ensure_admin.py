from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Ensure default admin superuser exists and has correct password and role.'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'AdminPass123!'
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': 'admin@example.com'},
        )
        user.set_password(password)
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        status = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' successfully {status} with role ADMIN."))
