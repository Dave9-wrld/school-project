from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


def token_expires_at(token):
    return token.created + timedelta(seconds=settings.API_TOKEN_TTL_SECONDS)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if timezone.now() >= token_expires_at(token):
            token.delete()
            raise AuthenticationFailed('Token expired. Log in again.')
        return user, token
