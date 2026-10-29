from datetime import timedelta
from unittest.mock import patch
import re
import uuid

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import User
from .models import PasswordResetChallenge


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class PasswordRecoveryTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('recovery_teacher', email='teacher@example.com',
                                             password='PreviousPass!492', role='TEACHER')

    def request_code(self, email='teacher@example.com', username='recovery_teacher'):
        return self.client.post('/api/password-reset/', {'username': username, 'email': email}, format='json')

    def emailed_code(self):
        return re.search(r'^([0-9]{6})$', mail.outbox[-1].body, re.MULTILINE).group(1)

    def confirm(self, challenge_id, code, password='FreshPass!937Blue', confirmation=None):
        return self.client.post('/api/password-reset/confirm/', {
            'challenge_id': challenge_id, 'code': code, 'new_password': password,
            'confirm_password': password if confirmation is None else confirmation,
        }, format='json')

    def test_full_recovery_revokes_token_session_and_preserves_role(self):
        token = Token.objects.create(user=self.user)
        self.client.force_login(self.user)
        response = self.request_code()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].to, ['teacher@example.com'])
        self.assertIn('10 minutes', mail.outbox[0].body)
        code = self.emailed_code()
        challenge_id = response.data['challenge_id']
        self.assertEqual(self.confirm(challenge_id, code).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, 'TEACHER')
        self.assertTrue(self.user.check_password('FreshPass!937Blue'))
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get('/api/teacher/subjects/').status_code, 401)
        self.assertEqual(self.confirm(challenge_id, code).status_code, 400)
        self.assertEqual(self.client.post('/api/login/', {'username': self.user.username, 'password': 'PreviousPass!492'}).status_code, 400)
        self.assertEqual(self.client.post('/api/login/', {'username': self.user.username, 'password': 'FreshPass!937Blue'}).status_code, 200)

    def test_unknown_inactive_and_unusable_accounts_are_indistinguishable(self):
        baseline = self.request_code().data
        mail.outbox.clear()
        for email, active, usable in [('missing@example.com', True, True), ('teacher@example.com', False, True), ('teacher@example.com', True, False)]:
            self.user.is_active = active
            if not usable:
                self.user.set_unusable_password()
            self.user.save()
            response = self.request_code(email)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.data), set(baseline))
            self.assertEqual(response.data['detail'], baseline['detail'])
            uuid.UUID(response.data['challenge_id'])
        self.assertEqual(len(mail.outbox), 0)

    def test_matching_username_selects_correct_account_for_shared_email(self):
        other = User.objects.create_user('other', email=self.user.email, password='OtherPass!99')
        response = self.request_code(email='TEACHER@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.username, mail.outbox[0].body)
        self.assertEqual(PasswordResetChallenge.objects.get().user_id, self.user.pk)
        self.assertFalse(PasswordResetChallenge.objects.filter(user=other).exists())
        self.assertEqual(self.request_code(username='wrong').status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_codes_preserve_leading_zero_and_are_not_stored_or_returned_plaintext(self):
        with patch('portal.password_reset.secrets.randbelow', return_value=12345):
            response = self.request_code()
        self.assertEqual(self.emailed_code(), '012345')
        self.assertNotIn('012345', str(response.data))
        challenge = PasswordResetChallenge.objects.get()
        self.assertNotIn('012345', challenge.code_digest)
        self.assertEqual(len(challenge.code_digest), 64)
        self.assertEqual(self.confirm(response.data['challenge_id'], '012345').status_code, 200)

    def test_expired_code_is_rejected(self):
        response = self.request_code()
        PasswordResetChallenge.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.confirm(response.data['challenge_id'], self.emailed_code()).status_code, 400)

    def test_five_wrong_attempts_lock_out_correct_code(self):
        response = self.request_code()
        code = self.emailed_code()
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.confirm(response.data['challenge_id'], wrong).status_code, 400)
        self.assertEqual(self.confirm(response.data['challenge_id'], code).status_code, 400)
        self.assertEqual(PasswordResetChallenge.objects.get().attempts, 5)

    def test_resend_replaces_previous_challenge(self):
        first = self.request_code()
        old_code = self.emailed_code()
        second = self.request_code()
        new_code = self.emailed_code()
        self.assertNotEqual(first.data['challenge_id'], second.data['challenge_id'])
        self.assertEqual(PasswordResetChallenge.objects.count(), 1)
        self.assertEqual(self.confirm(first.data['challenge_id'], old_code).status_code, 400)
        self.assertEqual(self.confirm(second.data['challenge_id'], new_code).status_code, 200)

    def test_password_validation_and_mismatch_do_not_consume_code(self):
        response = self.request_code()
        challenge_id, code = response.data['challenge_id'], self.emailed_code()
        self.assertEqual(self.confirm(challenge_id, code, '12345678').status_code, 400)
        self.assertEqual(self.confirm(challenge_id, code, confirmation='DoesNotMatch!17').status_code, 400)
        self.assertEqual(self.confirm(challenge_id, code).status_code, 200)

    def test_changes_to_account_invalidate_outstanding_code(self):
        for field, value in [('password', 'ChangedPass!90'), ('email', 'updated@example.com'), ('is_active', False)]:
            cache.clear()
            self.user.email = 'teacher@example.com'
            self.user.is_active = True
            self.user.save()
            response = self.request_code()
            code = self.emailed_code()
            if field == 'password':
                self.user.set_password(value)
            else:
                setattr(self.user, field, value)
            self.user.save()
            self.assertEqual(self.confirm(response.data['challenge_id'], code).status_code, 400)

    def test_malformed_inputs_and_legacy_link_are_rejected(self):
        self.assertEqual(self.request_code('not-an-email').status_code, 400)
        self.assertEqual(self.client.post('/api/password-reset/', [], format='json').status_code, 400)
        self.assertEqual(self.confirm(str(uuid.uuid4()), '12345').status_code, 400)
        self.assertEqual(self.confirm(str(uuid.uuid4()), '123456').status_code, 400)
        self.assertEqual(self.client.post('/api/password-reset/confirm/', {'uid': 'MQ', 'token': 'old-link'}, format='json').status_code, 400)

    def test_request_and_confirm_throttles(self):
        for _ in range(3):
            self.assertEqual(self.request_code('missing@example.com').status_code, 200)
        self.assertEqual(self.request_code('missing@example.com').status_code, 429)
        cache.clear()
        for i in range(10):
            self.assertEqual(self.request_code(f'missing{i}@example.com').status_code, 200)
        self.assertEqual(self.request_code('another@example.com').status_code, 429)
        for _ in range(20):
            self.assertEqual(self.confirm(str(uuid.uuid4()), '123456').status_code, 400)
        self.assertEqual(self.confirm(str(uuid.uuid4()), '123456').status_code, 429)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_reports_unavailable_instead_of_fake_delivery(self):
        self.assertEqual(self.request_code().status_code, 503)
        self.assertEqual(self.request_code('missing@example.com').status_code, 503)
        self.assertFalse(PasswordResetChallenge.objects.exists())

    @patch('portal.password_reset.get_connection')
    def test_smtp_configuration_failure_is_unavailable_for_all_accounts(self, get_connection):
        get_connection.return_value.open.side_effect = OSError('SMTP unavailable')
        self.assertEqual(self.request_code().status_code, 503)
        self.assertEqual(self.request_code('missing@example.com').status_code, 503)
        self.assertFalse(PasswordResetChallenge.objects.exists())

    @patch('portal.password_reset.send_mail', side_effect=OSError('Delivery refused'))
    def test_failed_delivery_invalidates_unsent_challenge(self, send_mail):
        self.assertEqual(self.request_code().status_code, 200)
        self.assertFalse(PasswordResetChallenge.objects.exists())
