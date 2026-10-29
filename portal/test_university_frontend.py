from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from academics.models import Subject


class UniversityPortalTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(username='lecturer', role=User.Role.TEACHER)
        self.student = User.objects.create_user(username='student', first_name='Ada', last_name='Okafor')
        self.subject = Subject.objects.create(name='Mathematics', code='MAT101', teacher=self.teacher)

    def test_directory_requires_teacher_permission(self):
        url = reverse('api_teacher_students')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)
        admin = User.objects.create_user(username='admin', role=User.Role.ADMIN)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_directory_returns_only_active_students_and_minimal_fields(self):
        User.objects.create_user(username='inactive', is_active=False)
        former_student = User.objects.create_user(username='former_student')
        former_student.role = User.Role.TEACHER
        former_student.save()
        self.client.force_authenticate(self.teacher)
        response = self.client.get(reverse('api_teacher_students'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [{
            'id': self.student.student_profile.pk,
            'name': 'Ada Okafor',
            'username': 'student',
            'admission_number': '',
        }])

    def test_unassigned_lecturer_has_no_student_directory(self):
        other = User.objects.create_user(username='unassigned', role=User.Role.TEACHER)
        self.client.force_authenticate(other)
        response = self.client.get(reverse('api_teacher_students'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
