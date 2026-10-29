from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from academics.models import ClassRoom


class ClassManagementAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username='admin', role=User.Role.ADMIN)
        self.lecturer = User.objects.create_user(
            username='lecturer', first_name='Ada', last_name='Okafor', role=User.Role.TEACHER,
        )
        self.student = User.objects.create_user(
            username='student', first_name='Tomi', last_name='Bello', role=User.Role.STUDENT,
        )
        self.profile = self.student.student_profile

    def test_admin_creates_class_and_allocates_lecturer_and_student(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(reverse('api_admin_classes'), {
            'name': 'Year 1 A', 'class_teacher': self.lecturer.pk,
        })
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['teacher_name'], 'Ada Okafor')
        self.assertEqual(created.data['student_count'], 0)
        class_id = created.data['id']

        allocated = self.client.patch(
            reverse('api_admin_student_class', args=[self.profile.pk]),
            {'current_class': class_id},
        )
        self.assertEqual(allocated.status_code, 200, allocated.data)
        self.assertEqual(allocated.data['current_class_name'], 'Year 1 A')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_class_id, class_id)

        classes = self.client.get(reverse('api_admin_classes'))
        self.assertEqual(classes.data[0]['student_count'], 1)
        self.assertEqual(self.client.get(reverse('api_admin_students')).data[0]['current_class'], class_id)
        self.assertEqual(self.client.get(reverse('api_admin_teachers')).data[0]['id'], self.lecturer.pk)

        self.client.force_authenticate(self.lecturer)
        self.assertEqual(self.client.get(reverse('api_teacher_classes')).data[0]['name'], 'Year 1 A')
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(reverse('api_student_profile')).data['current_class_name'], 'Year 1 A')

    def test_only_admin_can_change_class_allocations(self):
        classroom = ClassRoom.objects.create(name='Year 2 B')
        urls = [
            reverse('api_admin_classes'),
            reverse('api_admin_class_detail', args=[classroom.pk]),
            reverse('api_admin_students'),
            reverse('api_admin_student_class', args=[self.profile.pk]),
            reverse('api_admin_teachers'),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)
        for user in (self.student, self.lecturer):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(urls[0], {'name': 'Forbidden'}).status_code, 403)
            self.assertEqual(self.client.patch(urls[1], {'class_teacher': self.lecturer.pk}).status_code, 403)
            self.assertEqual(self.client.patch(urls[3], {'current_class': classroom.pk}).status_code, 403)
        self.assertFalse(ClassRoom.objects.filter(name='Forbidden').exists())
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.current_class)

    def test_invalid_role_or_missing_class_does_not_change_records(self):
        self.client.force_authenticate(self.admin)
        classroom = ClassRoom.objects.create(name='Year 3 C')
        duplicate = self.client.post(reverse('api_admin_classes'), {'name': classroom.name})
        self.assertEqual(duplicate.status_code, 400)
        invalid_teacher = self.client.patch(
            reverse('api_admin_class_detail', args=[classroom.pk]),
            {'class_teacher': self.student.pk},
        )
        self.assertEqual(invalid_teacher.status_code, 400)
        invalid_class = self.client.patch(
            reverse('api_admin_student_class', args=[self.profile.pk]),
            {'current_class': 999999},
        )
        self.assertEqual(invalid_class.status_code, 400)
        classroom.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertIsNone(classroom.class_teacher)
        self.assertIsNone(self.profile.current_class)

    def test_admin_can_reassign_and_unassign(self):
        first = ClassRoom.objects.create(name='Class A')
        second = ClassRoom.objects.create(name='Class B', class_teacher=self.lecturer)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(
            reverse('api_admin_student_class', args=[self.profile.pk]),
            {'current_class': first.pk},
        ).status_code, 200)
        self.assertEqual(self.client.patch(
            reverse('api_admin_student_class', args=[self.profile.pk]),
            {'current_class': second.pk},
        ).status_code, 200)
        self.assertEqual(self.client.patch(
            reverse('api_admin_class_detail', args=[second.pk]),
            {'class_teacher': None},
            format='json',
        ).status_code, 200)
        self.assertEqual(self.client.patch(
            reverse('api_admin_student_class', args=[self.profile.pk]),
            {'current_class': None},
            format='json',
        ).status_code, 200)
        self.profile.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(self.profile.current_class)
        self.assertIsNone(second.class_teacher)
