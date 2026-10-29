"""Email OTP recovery. Codes are never returned by the API or stored in plaintext."""
from datetime import timedelta
import logging
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import get_connection, send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import PasswordResetChallenge
from .throttles import ResetEmailThrottle, ResetRequestThrottle, ResetConfirmThrottle

logger = logging.getLogger(__name__)
UNAVAILABLE = 'Password recovery is temporarily unavailable. Please contact the university administrator.'
INVALID = 'This code is incorrect, expired or no longer valid. Request a new code if needed.'


def code_digest(challenge_id, code):
    return salted_hmac('portal.recovery.code', f'{challenge_id}:{code}', algorithm='sha256').hexdigest()


def account_digest(user):
    return salted_hmac('portal.recovery.account', f'{user.password}:{user.email}', algorithm='sha256').hexdigest()


class ResetRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)


class ResetConfirmSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r'\A[0-9]{6}\Z', max_length=6, trim_whitespace=True)
    new_password = serializers.CharField(trim_whitespace=False, max_length=4096)
    confirm_password = serializers.CharField(trim_whitespace=False, max_length=4096)


class PasswordResetRequestAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResetRequestThrottle, ResetEmailThrottle]

    def post(self, request):
        serializer = ResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # In production (DEBUG=False), never claim to send mail while printing locally.
        if not settings.DEBUG and settings.EMAIL_BACKEND in ('django.core.mail.backends.console.EmailBackend', 'django.core.mail.backends.dummy.EmailBackend'):
            logger.warning('Password recovery unavailable: configure a delivering email backend.')
            return Response({'detail': UNAVAILABLE}, status=503)
        connection = get_connection()
        try:
            # Check SMTP even for unknown accounts, without revealing account existence.
            connection.open()
        except Exception:
            if not settings.DEBUG:
                logger.error('Password recovery mail connection failed. Check SMTP configuration.')
                return Response({'detail': UNAVAILABLE}, status=503)
        challenge_id = uuid.uuid4()
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(
                    username=data['username'], email__iexact=data['email'], is_active=True,
                ).first()
                if user and user.has_usable_password():
                    code = f'{secrets.randbelow(1_000_000):06d}'
                    PasswordResetChallenge.objects.update_or_create(user=user, defaults={
                        'challenge_id': challenge_id,
                        'code_digest': code_digest(challenge_id, code),
                        'account_digest': account_digest(user),
                        'expires_at': timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_OTP_SECONDS),
                        'attempts': 0,
                    })
                else:
                    code = None
            if code:
                try:
                    sent = send_mail(
                        'Your Dave University password reset code',
                        f'Hello {user.username},\n\nYour password reset code is:\n\n{code}\n\n'
                        f'Enter it in the portal where you requested it. It expires in {settings.PASSWORD_RESET_OTP_SECONDS // 60} minutes '
                        'and can only be used once. Requesting a new code replaces this one.\n\n'
                        'If you did not request this, ignore this email. Never share this code.\n\nDave University',
                        settings.DEFAULT_FROM_EMAIL, [user.email], connection=connection,
                    )
                    if not sent:
                        raise RuntimeError('Email backend did not send the message')
                except Exception:
                    PasswordResetChallenge.objects.filter(challenge_id=challenge_id).delete()
                    logger.error('Password recovery email delivery failed. Check mail provider logs.')
                    # Recipient-specific failures must not expose account existence.
        finally:
            connection.close()
        return Response({
            'detail': 'If the username and email match an eligible account, a six-digit code will arrive shortly. Check your inbox and spam folder.',
            'challenge_id': str(challenge_id),
            'expires_in': settings.PASSWORD_RESET_OTP_SECONDS,
        })


class PasswordResetConfirmAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResetConfirmThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = ResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Conditional write claims an attempt atomically, including on SQLite.
        updated = PasswordResetChallenge.objects.filter(
            challenge_id=data['challenge_id'], expires_at__gt=timezone.now(),
            attempts__lt=settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS,
        ).update(attempts=F('attempts') + 1)
        if not updated:
            return Response({'detail': INVALID}, status=400)
        challenge = PasswordResetChallenge.objects.select_for_update().get(challenge_id=data['challenge_id'])
        user = User.objects.select_for_update().get(pk=challenge.user_id)
        if (not user.is_active or not user.has_usable_password()
                or not constant_time_compare(challenge.account_digest, account_digest(user))
                or not constant_time_compare(challenge.code_digest, code_digest(challenge.challenge_id, data['code']))):
            return Response({'detail': INVALID}, status=400)
        form = SetPasswordForm(user, {'new_password1': data['new_password'], 'new_password2': data['confirm_password']})
        if not form.is_valid():
            return Response({'detail': ' '.join(message for errors in form.errors.values() for message in errors)}, status=400)
        form.save()
        Token.objects.filter(user=user).delete()
        challenge.delete()
        return Response({'detail': 'Your password has been changed. Sign in with your new password.'})
