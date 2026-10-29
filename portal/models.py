from django.db import models
from django.conf import settings
import uuid


class PasswordResetChallenge(models.Model):
    # At most one outstanding code per account; resending replaces it.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    challenge_id = models.UUIDField(default=uuid.uuid4, unique=True)
    code_digest = models.CharField(max_length=64)
    account_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
