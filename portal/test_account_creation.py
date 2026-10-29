from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import User, StudentProfile, TeacherProfile
from portal.serializers import UserSerializer, StudentProfileSerializer


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountCreationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.payload = {'username': 'new_student', 'password': 'River!Cloud-7294',
                        'email': 'student@example.com', 'admission_number': 'DU/26/009'}

    def register(self, **changes):
        return self.client.post(reverse('api_register'), {**self.payload, **changes}, format='json')

    def test_registration_response_and_profile_align_with_token_authentication(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username=self.payload['username'])
        self.assertEqual(user.student_profile.admission_number, self.payload['admission_number'])
        self.assertEqual(response.data['user']['admission_number'], self.payload['admission_number'])
        self.assertEqual(response.data['user']['role'], 'STUDENT')
        self.assertNotIn('password', response.data['user'])
        self.assertIn('expires_at', response.data)
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertEqual(Token.objects.get(user=user).key, response.data['token'])
        self.client.credentials(HTTP_AUTHORIZATION='Token '+response.data['token'])
        profile = self.client.get(reverse('api_student_profile'))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data['admission_number'], self.payload['admission_number'])
        self.assertEqual(self.client.get(reverse('api_students_grade')).status_code, 200)

    def test_public_registration_ignores_stale_auth_and_cannot_create_lecturers(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        response = self.register(role='TEACHER', is_staff=True, is_superuser=True)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username=self.payload['username'])
        self.assertEqual(user.role, 'STUDENT')
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(TeacherProfile.objects.filter(user=user).exists())

    def test_duplicate_admission_number_is_400_and_creates_no_partial_user(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register(username='duplicate_student')
        self.assertEqual(response.status_code, 400)
        self.assertIn('admission_number', response.data)
        self.assertFalse(User.objects.filter(username='duplicate_student').exists())
        self.assertEqual(StudentProfile.objects.count(), 1)

    def test_blank_numbers_are_optional_and_overlong_or_wrong_ids_are_rejected(self):
        for i in range(2):
            self.assertEqual(self.register(username=f'blank{i}', admission_number='').status_code, 201)
        self.assertEqual(StudentProfile.objects.filter(admission_number__isnull=True).count(), 2)
        self.assertEqual(self.register(admission_number='x'*21).status_code, 400)
        self.assertEqual(self.register(employee_id='EMP1').status_code, 400)
        self.assertFalse(User.objects.filter(username=self.payload['username']).exists())

    def test_token_failure_rolls_back_registration(self):
        with patch('portal.api_views.Token.objects.get_or_create', side_effect=RuntimeError('token failed')):
            with self.assertRaises(RuntimeError):
                self.register()
        self.assertFalse(User.objects.exists())
        self.assertFalse(StudentProfile.objects.exists())

    def test_admin_endpoint_permissions(self):
        url = reverse('api_admin_users')
        self.assertEqual(self.client.post(url, self.payload).status_code, 401)
        for role in ('STUDENT', 'TEACHER'):
            actor = User.objects.create_user(username=role, role=role)
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.post(url, self.payload).status_code, 403)

    def test_admin_creates_lecturer_employee_id_without_changing_admin_session(self):
        admin = User.objects.create_user(username='admin', role='ADMIN')
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION='Token '+admin_token.key)
        payload = {'username': 'new_lecturer', 'password': 'Forest!Moon-7392', 'role': 'TEACHER',
                   'employee_id': 'EMP-123', 'email': 'lecturer@example.com'}
        response = self.client.post(reverse('api_admin_users'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        lecturer = User.objects.get(username=payload['username'])
        self.assertEqual(lecturer.teacher_profile.employee_id, 'EMP-123')
        self.assertEqual(response.data['employee_id'], 'EMP-123')
        self.assertTrue(lecturer.check_password(payload['password']))
        self.assertFalse(lecturer.is_staff)
        self.assertNotIn('password', response.data)
        self.assertNotIn('token', response.data)
        self.assertFalse(Token.objects.filter(user=lecturer).exists())
        self.assertEqual(self.client.get(reverse('api_admin_teachers')).data[0]['employee_id'], 'EMP-123')
        duplicate = self.client.post(reverse('api_admin_users'), {**payload, 'username': 'duplicate'}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('employee_id', duplicate.data)
        self.assertFalse(User.objects.filter(username='duplicate').exists())
        self.assertEqual(self.client.get(reverse('api_admin_stats')).status_code, 200)

    def test_admin_student_creation_validates_password_and_rejects_invalid_roles(self):
        self.client.force_authenticate(User.objects.create_user(username='admin', role='ADMIN'))
        url = reverse('api_admin_users')
        for changes in ({'password':'123456'}, {'role':'ADMIN'}, {'role':'TEACHER'}, {'employee_id':'EMP1'}):
            self.assertEqual(self.client.post(url, {**self.payload, **changes}, format='json').status_code, 400)
        self.assertFalse(User.objects.filter(username=self.payload['username']).exists())
        response = self.client.post(url, {**self.payload, 'role':'STUDENT'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['admission_number'], 'DU/26/009')

    def test_read_serializers_never_expose_passwords(self):
        student = User.objects.create_user(username='student', password=self.payload['password'])
        teacher = User.objects.create_user(username='teacher', role='TEACHER', password=self.payload['password'])
        for user in (student, teacher):
            self.assertNotIn('password', UserSerializer(user).data)
        self.assertNotIn('password', StudentProfileSerializer(student.student_profile).data['user'])
