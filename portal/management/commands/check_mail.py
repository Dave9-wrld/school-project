from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Check SMTP connection and credentials without sending an email.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            raise CommandError('SMTP delivery is not enabled. Use scripts/start_with_gmail.ps1.')
        try:
            with get_connection() as connection:
                connection.open()
        except Exception:
            raise CommandError('Gmail connection failed. Check your address, App Password and network connection.') from None
        self.stdout.write(self.style.SUCCESS('SMTP connection and authentication succeeded.'))
