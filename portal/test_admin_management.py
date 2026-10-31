from django.urls import reverse
from rest_framework.test import APITestCase
from accounts.models import User, StudentProfile, TeacherProfile
from academics.models import AcademicSession, ClassRoom, Subject, Grade


class AdminManagementAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin_boss', password='password123', role=User.Role.ADMIN, is_staff=True)
        self.teacher = User.objects.create_user(username='prof_smith', password='password123', role=User.Role.TEACHER, first_name='John', last_name='Smith')
        self.student_user = User.objects.create_user(username='student_alice', password='password123', role=User.Role.STUDENT, first_name='Alice', last_name='Wonder')
        self.student_profile = self.student_user.student_profile
        self.session = AcademicSession.objects.create(session='2025/2026', is_current=True)
        self.classroom = ClassRoom.objects.create(name='Grade 10', class_teacher=self.teacher)
        self.subject = Subject.objects.create(name='Physics', code='PHY101', teacher=self.teacher)
        self.client.force_authenticate(self.admin)

    def test_admin_sessions_crud(self):
        # List sessions
        res = self.client.get(reverse('api_admin_sessions'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

        # Create new session
        res = self.client.post(reverse('api_admin_sessions'), {'session': '2026/2027', 'is_current': True})
        self.assertEqual(res.status_code, 201)
        new_id = res.data['id']
        self.assertTrue(res.data['is_current'])

        # Previous session must no longer be current
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_current)

        # Patch session
        res = self.client.patch(reverse('api_admin_session_detail', args=[self.session.pk]), {'is_current': True})
        self.assertEqual(res.status_code, 200)
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_current)

        # Delete new session
        del_res = self.client.delete(reverse('api_admin_session_detail', args=[new_id]))
        self.assertEqual(del_res.status_code, 204)
        self.assertFalse(AcademicSession.objects.filter(pk=new_id).exists())

    def test_admin_subjects_crud(self):
        # List subjects
        res = self.client.get(reverse('api_admin_subjects'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

        # Create subject
        res = self.client.post(reverse('api_admin_subjects'), {'name': 'Chemistry', 'code': 'CHM101', 'teacher': self.teacher.pk})
        self.assertEqual(res.status_code, 201)
        chem_id = res.data['id']
        self.assertEqual(res.data['teacher'], self.teacher.pk)

        # Patch subject
        res = self.client.patch(reverse('api_admin_subject_detail', args=[chem_id]), {'name': 'Advanced Chemistry'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['name'], 'Advanced Chemistry')

        # Delete subject
        res = self.client.delete(reverse('api_admin_subject_detail', args=[chem_id]))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Subject.objects.filter(pk=chem_id).exists())

    def test_admin_student_management(self):
        # Update student profile
        res = self.client.patch(reverse('api_admin_student_detail', args=[self.student_profile.pk]), {
            'admission_number': 'ADM/2026/001',
            'current_class': self.classroom.pk,
            'phone_number': '08012345678',
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['admission_number'], 'ADM/2026/001')
        self.assertEqual(res.data['current_class'], self.classroom.pk)

        # Delete student
        res = self.client.delete(reverse('api_admin_student_detail', args=[self.student_profile.pk]))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(User.objects.filter(username='student_alice').exists())

    def test_admin_teacher_management(self):
        # Update teacher
        res = self.client.patch(reverse('api_admin_teacher_detail', args=[self.teacher.pk]), {
            'department': 'Science',
            'employee_id': 'EMP-500',
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['department'], 'Science')
        self.assertEqual(res.data['employee_id'], 'EMP-500')

    def test_admin_grades_management(self):
        # Create grade
        res = self.client.post(reverse('api_admin_grades'), {
            'student': self.student_profile.pk,
            'subject': self.subject.pk,
            'session': self.session.pk,
            'continuous_assessment_score': '35.00',
            'exam_score': '55.00',
        })
        self.assertEqual(res.status_code, 201)
        grade_id = res.data['id']
        self.assertEqual(float(res.data['total_score']), 90.0)

        # List grades
        res = self.client.get(reverse('api_admin_grades'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

        # Update grade
        res = self.client.patch(reverse('api_admin_grade_detail', args=[grade_id]), {
            'exam_score': '58.00',
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(float(res.data['total_score']), 93.0)

        # Delete grade
        res = self.client.delete(reverse('api_admin_grade_detail', args=[grade_id]))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Grade.objects.filter(pk=grade_id).exists())
