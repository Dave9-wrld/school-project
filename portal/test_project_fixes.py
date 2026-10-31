from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import User, StudentProfile, TeacherProfile
from academics.models import AcademicSession, Grade, Subject
from portal.throttles import LoginRateThrottle, RegistrationRateThrottle


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProjectFixTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = 'River!Cloud-7294'
        self.teacher = User.objects.create_user(username='teacher', password=self.password, role='TEACHER')
        self.student = User.objects.create_user(username='student', password=self.password, role='STUDENT')
        self.admin = User.objects.create_user(username='school_admin', role='ADMIN')
        self.session = AcademicSession.objects.create(session='2026/2027', is_current=True)
        self.subject = Subject.objects.create(name='Math', code='MATH', teacher=self.teacher)
        self.profile = self.student.student_profile
        self.grade_url = reverse('api_teacher_grades', args=[self.subject.pk])
        self.form_url = reverse('record_grade', args=[self.subject.pk])

    def test_login_page_and_invalid_credentials_render(self):
        self.assertContains(self.client.get(reverse('login')), 'Log in')
        response = self.client.post(reverse('login'), {'username': 'student', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')

    def test_browser_login_redirects_to_working_dashboard(self):
        response = self.client.post(reverse('login'), {'username': 'student', 'password': self.password}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student academic record')

    def test_dashboard_counts_subjects_and_results_render(self):
        Grade.objects.create(student=self.profile, subject=self.subject, session=self.session,
                             continuous_assessment_score=Decimal('30.00'), exam_score=Decimal('50.00'))
        for user, route, expected in (
            (self.admin, 'admin_dashboard', 'School overview'),
            (self.teacher, 'teacher_dashboard', 'MATH'),
            (self.student, 'student_dashboard', '80.00'),
        ):
            with self.subTest(route=route):
                self.client.force_login(user)
                response = self.client.get(reverse(route))
                self.assertContains(response, expected)
                if route == 'admin_dashboard':
                    self.assertEqual(response.context['total_students'], 1)
                    self.assertEqual(response.context['total_subjects'], 1)
                if route == 'student_dashboard':
                    self.assertContains(response, '2026/2027')
                    self.assertContains(response, '<td>Math</td>', count=1)

    def test_grade_form_creates_and_updates_scores(self):
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(self.form_url), 'Save grade')
        payload = {'student': self.profile.pk, 'continuous_assessment_score': '30', 'exam_score': '50'}
        self.assertEqual(self.client.post(self.form_url, payload).status_code, 302)
        payload['continuous_assessment_score'] = '35'
        self.assertEqual(self.client.post(self.form_url, payload).status_code, 302)
        self.assertEqual(Grade.objects.count(), 1)
        grade = Grade.objects.get()
        self.assertEqual(grade.continuous_assessment_score, 35)
        self.assertEqual(grade.total_score(), 85)

    def test_grade_form_rejects_invalid_scores_and_student(self):
        self.client.force_login(self.teacher)
        for changes in ({'exam_score': '61'}, {'continuous_assessment_score': '-1'}, {'student': 999999}, {'exam_score': 'bad'}):
            payload = {'student': self.profile.pk, 'continuous_assessment_score': '30', 'exam_score': '50', **changes}
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(self.form_url, payload).status_code, 400)
        self.assertFalse(Grade.objects.exists())

    def test_grade_form_handles_missing_session(self):
        self.session.is_current = False
        self.session.save()
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(self.form_url), 'No current academic session')
        response = self.client.post(self.form_url, {'student': self.profile.pk, 'continuous_assessment_score': '30', 'exam_score': '50'})
        self.assertContains(response, 'No current academic session', status_code=400)
        self.assertFalse(Grade.objects.exists())

    def test_html_grade_form_preserves_role_and_subject_permissions(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.form_url).status_code, 403)
        other = User.objects.create_user(username='other_teacher', role='TEACHER')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.form_url).status_code, 404)

    def test_api_score_limits_on_create_and_update(self):
        self.client.force_authenticate(self.teacher)
        for field, value in (('continuous_assessment_score', '-1'), ('continuous_assessment_score', '40.01'),
                             ('exam_score', '-1'), ('exam_score', '60.01')):
            with self.subTest(field=field, value=value):
                response = self.client.post(self.grade_url, {'student': self.profile.pk, field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(Grade.objects.exists())
        self.assertEqual(self.client.post(self.grade_url, {'student': self.profile.pk, 'continuous_assessment_score': '40', 'exam_score': '60'}).status_code, 201)
        self.assertEqual(self.client.post(self.grade_url, {'student': self.profile.pk, 'exam_score': '61'}).status_code, 400)
        self.assertEqual(Grade.objects.get().total_score(), 100)
        self.assertEqual(self.client.post(self.grade_url, {'student': self.profile.pk, 'continuous_assessment_score': '0', 'exam_score': '0'}).status_code, 200)

    def test_database_rejects_out_of_range_grades(self):
        for values in ({'exam_score': 61}, {'exam_score': -1}, {'continuous_assessment_score': 41}, {'continuous_assessment_score': -1}):
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Grade.objects.create(student=self.profile, subject=self.subject, session=self.session, **values)
        self.assertFalse(Grade.objects.exists())

    def test_only_one_current_session_and_switching(self):
        other = AcademicSession.objects.create(session='2027/2028')
        other.is_current = True
        with self.assertRaises(ValidationError):
            other.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            other.save()
        self.session.is_current = False
        self.session.save()
        other.save()
        self.assertEqual(AcademicSession.objects.get(is_current=True), other)

    def test_profiles_exist_and_repeated_saves_do_not_duplicate(self):
        for user in (self.student, self.teacher):
            user.save()
            user.save()
        self.assertEqual(StudentProfile.objects.filter(user=self.student).count(), 1)
        self.assertEqual(TeacherProfile.objects.filter(user=self.teacher).count(), 1)
        self.assertFalse(StudentProfile.objects.filter(user=self.teacher).exists())
        self.assertFalse(TeacherProfile.objects.filter(user=self.admin).exists())

    def test_role_change_creates_new_profile_without_deleting_old_records(self):
        self.student.role = 'TEACHER'
        self.student.save()
        self.assertTrue(TeacherProfile.objects.filter(user=self.student).exists())
        self.assertTrue(StudentProfile.objects.filter(user=self.student).exists())

    def test_profile_backfill_handles_legacy_users_and_is_idempotent(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        StudentProfile.objects.filter(user=self.student).delete()
        TeacherProfile.objects.filter(user=self.teacher).delete()
        backfill = import_module('accounts.migrations.0002_backfill_profiles').backfill_profiles
        from types import SimpleNamespace
        editor = SimpleNamespace(connection=connection)
        backfill(apps, editor)
        backfill(apps, editor)
        self.assertEqual(StudentProfile.objects.filter(user=self.student).count(), 1)
        self.assertEqual(TeacherProfile.objects.filter(user=self.teacher).count(), 1)

    def test_token_expiry_blocks_access(self):
        token = Token.objects.create(user=self.student)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=25))
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.get(reverse('api_students_grade'))
        self.assertEqual(response.status_code, 401)
        self.assertIn('expired', str(response.data))
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_login_replaces_expired_token_and_returns_expiry(self):
        token = Token.objects.create(user=self.student)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=25))
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.post(reverse('api_login'), {'username': 'student', 'password': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data['token'], token.key)
        self.assertIn('expires_at', response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + response.data['token'])
        self.assertEqual(self.client.get(reverse('api_students_grade')).status_code, 200)

    def test_api_logout_revokes_token_and_session(self):
        token = Token.objects.create(user=self.student)
        self.client.force_login(self.student)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.post(reverse('api_logout'))
        self.assertEqual(response.status_code, 204)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertFalse(Token.objects.filter(user=self.student).exists())
        self.assertEqual(self.client.get(reverse('api_students_grade')).status_code, 401)

    def test_browser_logout_revokes_token(self):
        self.client.force_login(self.student)
        token = Token.objects.create(user=self.student)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(self.client.get(reverse('api_students_grade')).status_code, 401)

    def test_password_change_revokes_token_but_normal_save_does_not(self):
        token = Token.objects.create(user=self.student)
        self.student.first_name = 'Student'
        self.student.save()
        self.assertTrue(Token.objects.filter(pk=token.pk).exists())
        self.student.set_password('New-pass-8294!')
        self.student.save(update_fields=['password'])
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_api_and_browser_logins_share_rate_limit(self):
        with patch.object(LoginRateThrottle, 'rate', '2/minute', create=True):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('api_login'), {'username': 'student', 'password': 'wrong'}).status_code, 400)
            for url in (reverse('api_login'), reverse('login'), '/api-auth/login/', '/admin/login/'):
                with self.subTest(url=url):
                    response = self.client.post(url, {'username': 'student', 'password': self.password})
                    self.assertEqual(response.status_code, 429)
                    self.assertIn('Retry-After', response)

    def test_registration_rate_limit(self):
        with patch.object(RegistrationRateThrottle, 'rate', '2/hour', create=True):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('api_register'), {}).status_code, 400)
            response = self.client.post(reverse('api_register'), {'username': 'another', 'password': self.password})
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)
            self.assertFalse(User.objects.filter(username='another').exists())

