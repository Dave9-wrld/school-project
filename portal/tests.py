from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APITestCase

from accounts.models import StudentProfile, User
from academics.models import AcademicSession, Grade, Subject


class MigrationRecoveryAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(username='teacher', password='test-password', role=User.Role.TEACHER)
        self.student = User.objects.create_user(username='student', role=User.Role.STUDENT)
        self.profile = self.student.student_profile
        self.session = AcademicSession.objects.create(session='2026/2027', is_current=True)
        self.subject = Subject.objects.create(name='Math', code='MATH', teacher=self.teacher)

    def test_api_index_is_public_and_does_not_redirect_logged_in_users(self):
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 19)
        self.client.force_login(self.teacher)
        response = self.client.get('/api/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/api/teacher/subjects/')
        self.assertContains(response, '/api-auth/logout/')

    def test_browser_session_authentication_and_csrf(self):
        from rest_framework.test import APIClient

        browser = APIClient(enforce_csrf_checks=True)
        self.assertEqual(browser.get('/api-auth/login/').status_code, 200)
        browser.force_login(self.teacher)
        self.assertEqual(browser.get(reverse('api_teacher_subjects')).status_code, 200)
        self.assertEqual(browser.get(reverse('api_admin_stats')).status_code, 403)
        # Browser writes must still include a CSRF token.
        self.assertEqual(browser.post(reverse('api_teacher_grades', args=[self.subject.pk]), {
            'student': self.profile.pk, 'exam_score': '60.00',
        }).status_code, 403)
        response = browser.get(reverse('api_teacher_grades', args=[self.subject.pk]), HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 405)
        csrf = browser.cookies['csrftoken'].value
        response = browser.post(reverse('api_teacher_grades', args=[self.subject.pk]), {
            'student': self.profile.pk, 'exam_score': '60.00',
        }, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201, response.data)

    def test_token_login_authenticates_teacher(self):
        response = self.client.post(reverse('api_login'), {'username': 'teacher', 'password': 'test-password'})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + response.data['token'])
        response = self.client.get(reverse('api_teacher_subjects'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], self.subject.pk)

    def test_role_permissions(self):
        for name in ('api_admin_stats', 'api_teacher_subjects', 'api_students_grade'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 401)
        self.client.force_authenticate(self.student)
        for name in ('api_admin_stats', 'api_teacher_subjects'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(reverse('api_students_grade')).status_code, 403)

    def test_grade_create_update_and_student_isolation(self):
        self.client.force_authenticate(self.teacher)
        url = reverse('api_teacher_grades', args=[self.subject.pk])
        response = self.client.post(url, {
            'student': self.profile.pk,
            'continous_assessment_score': '20.00',
            'exam_score': '60.00',
        })
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post(url, {'student': self.profile.pk, 'exam_score': '55.00'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Grade.objects.count(), 1)
        self.assertEqual(Grade.objects.get().total_score(), 75)

        other = User.objects.create_user(username='other', role=User.Role.STUDENT)
        other_profile = other.student_profile
        Grade.objects.create(student=other_profile, subject=self.subject, session=self.session)
        self.client.force_authenticate(self.student)
        response = self.client.get(reverse('api_students_grade'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['student'], self.profile.pk)

    def test_teacher_cannot_grade_another_teachers_subject(self):
        other = User.objects.create_user(username='other-teacher', role=User.Role.TEACHER)
        self.client.force_authenticate(other)
        response = self.client.post(reverse('api_teacher_grades', args=[self.subject.pk]), {
            'student': self.profile.pk, 'exam_score': '60.00',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Grade.objects.exists())

    def test_lecturer_results_list_only_includes_assigned_courses(self):
        other_teacher = User.objects.create_user(username='other-teacher', role=User.Role.TEACHER)
        other_subject = Subject.objects.create(name='History', code='HIST', teacher=other_teacher)
        Grade.objects.create(student=self.profile, subject=self.subject, session=self.session,
                             continous_assessment_score=20, exam_score=40)
        Grade.objects.create(student=self.profile, subject=other_subject, session=self.session,
                             continous_assessment_score=10, exam_score=30)

        url = reverse('api_teacher_grades_list')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.teacher)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['student_name'], 'student')
        self.assertEqual(response.data[0]['subject_name'], 'Math')
        self.assertEqual(str(response.data[0]['total_score']), '60.00')
        self.client.force_authenticate(other_teacher)
        response = self.client.get(url)
        self.assertEqual([grade['subject_name'] for grade in response.data], ['History'])

    def test_missing_student_profile_returns_404(self):
        self.profile.delete()
        self.student.refresh_from_db()
        self.client.force_authenticate(self.student)
        response = self.client.get(reverse('api_students_grade'))
        self.assertEqual(response.status_code, 404)

    def test_admin_stats(self):
        admin = User.objects.create_user(username='admin', role=User.Role.ADMIN)
        self.client.force_authenticate(admin)
        response = self.client.get(reverse('api_admin_stats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'total_teachers': 1, 'total_students': 1, 'total_subjects': 1,
        })

    def test_invalid_login_and_token(self):
        response = self.client.post(reverse('api_login'), {'username': 'teacher', 'password': 'wrong'})
        self.assertEqual(response.status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(self.client.get(reverse('api_teacher_subjects')).status_code, 401)

    def test_teacher_subjects_excludes_unassigned_subjects(self):
        Subject.objects.create(name='English', code='ENG')
        self.client.force_authenticate(self.teacher)
        response = self.client.get(reverse('api_teacher_subjects'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [self.subject.pk])

    def test_grade_requires_current_session(self):
        self.session.is_current = False
        self.session.save()
        self.client.force_authenticate(self.teacher)
        response = self.client.post(reverse('api_teacher_grades', args=[self.subject.pk]), {
            'student': self.profile.pk, 'exam_score': '60.00',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Grade.objects.exists())

    def test_invalid_grade_input_returns_400(self):
        self.client.force_authenticate(self.teacher)
        url = reverse('api_teacher_grades', args=[self.subject.pk])
        for payload in (
            {'student': 'invalid'},
            {'student': 999999},
            {},
            {'student': self.profile.pk, 'exam_score': 'invalid'},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        self.assertFalse(Grade.objects.exists())

    def test_grade_write_requires_teacher(self):
        url = reverse('api_teacher_grades', args=[self.subject.pk])
        self.assertEqual(self.client.post(url, {}).status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(url, {}).status_code, 403)


class RegistrationAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.payload = {'username': 'mr_victory', 'password': 'River!Cloud-7294'}

    def test_registration_then_login_and_student_grades(self):
        response = self.client.post(reverse('api_register'), self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        user = User.objects.get(username=self.payload['username'])
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertNotEqual(user.password, self.payload['password'])
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        response = self.client.post(reverse('api_login'), self.payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + response.data['token'])
        response = self.client.get(reverse('api_students_grade'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_duplicate_username_returns_validation_error(self):
        self.assertEqual(self.client.post(reverse('api_register'), self.payload, format='json').status_code, 201)
        response = self.client.post(reverse('api_register'), self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.data)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(StudentProfile.objects.count(), 1)

    def test_invalid_registration_creates_nothing(self):
        for changes, field in (
            ({'password': '123456'}, 'password'),
            ({'password': ''}, 'password'),
            ({'username': 'mr victory'}, 'username'),
            ({'username': ''}, 'username'),
            ({'email': 'invalid'}, 'email'),
        ):
            with self.subTest(field=field, changes=changes):
                response = self.client.post(reverse('api_register'), {**self.payload, **changes}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        response = self.client.post(reverse('api_register'), {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data)
        self.assertFalse(User.objects.exists())
        self.assertFalse(StudentProfile.objects.exists())

    def test_signup_cannot_assign_privileged_roles(self):
        payload = {**self.payload, 'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
        response = self.client.post(reverse('api_register'), payload, format='json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username=self.payload['username'])
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_profile_failure_rolls_back_user(self):
        from unittest.mock import patch

        with patch('portal.serializers.StudentProfile.objects.get_or_create', side_effect=RuntimeError('profile failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('api_register'), self.payload, format='json')
        self.assertFalse(User.objects.exists())
