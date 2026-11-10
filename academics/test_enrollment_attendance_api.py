from datetime import date, time

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from academics.models import (
    AcademicSession,
    AttendanceRecord,
    AttendanceSession,
    CourseEnrollment,
    Subject,
)


class EnrollmentAttendanceAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', role=User.Role.ADMIN)
        self.teacher = User.objects.create_user(username='teacher', role=User.Role.TEACHER)
        self.other_teacher = User.objects.create_user(username='other-teacher', role=User.Role.TEACHER)
        self.student = User.objects.create_user(username='student', role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username='other-student', role=User.Role.STUDENT)
        self.academic_session = AcademicSession.objects.create(session='2026/2027', is_current=True)
        self.subject = Subject.objects.create(name='Computer Science', code='CSC101', teacher=self.teacher)
        self.other_subject = Subject.objects.create(name='Economics', code='ECO101', teacher=self.other_teacher)
        self.enrollment = CourseEnrollment.objects.create(
            student=self.student.student_profile,
            subject=self.subject,
            session=self.academic_session,
        )
        self.other_enrollment = CourseEnrollment.objects.create(
            student=self.other_student.student_profile,
            subject=self.other_subject,
            session=self.academic_session,
        )

    def test_only_admin_can_create_course_enrollment(self):
        payload = {
            'student': self.other_student.student_profile.pk,
            'subject': self.subject.pk,
            'session': self.academic_session.pk,
        }
        url = reverse('api_course_enrollments')

        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['student_name'], 'other-student')
        self.assertEqual(CourseEnrollment.objects.count(), 3)

    def test_enrollment_lists_are_scoped_by_role(self):
        url = reverse('api_course_enrollments')

        self.client.force_authenticate(self.student)
        response = self.client.get(url)
        self.assertEqual([item['id'] for item in response.data], [self.enrollment.pk])

        self.client.force_authenticate(self.teacher)
        response = self.client.get(url)
        self.assertEqual([item['id'] for item in response.data], [self.enrollment.pk])

        self.client.force_authenticate(self.admin)
        response = self.client.get(url)
        self.assertEqual({item['id'] for item in response.data}, {self.enrollment.pk, self.other_enrollment.pk})

    def test_teacher_opens_only_an_assigned_course_session(self):
        url = reverse('api_attendance_sessions')
        payload = {
            'subject': self.subject.pk,
            'date': '2026-11-10',
            'starts_at': '09:00',
            'ends_at': '10:00',
        }
        self.client.force_authenticate(self.teacher)
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['academic_session'], self.academic_session.pk)
        self.assertEqual(AttendanceSession.objects.get().created_by, self.teacher)

        payload['subject'] = self.other_subject.pk
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('subject', response.data)

        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(url, payload).status_code, 403)

    def test_attendance_record_requires_matching_active_enrollment(self):
        attendance_session = AttendanceSession.objects.create(
            subject=self.subject,
            academic_session=self.academic_session,
            date=date(2026, 11, 10),
            starts_at=time(9, 0),
            created_by=self.teacher,
        )
        url = reverse('api_attendance_records')
        self.client.force_authenticate(self.teacher)

        response = self.client.post(url, {
            'attendance_session': attendance_session.pk,
            'course_enrollment': self.other_enrollment.pk,
            'status': AttendanceRecord.Status.PRESENT,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('course_enrollment', response.data)

        response = self.client.post(url, {
            'attendance_session': attendance_session.pk,
            'course_enrollment': self.enrollment.pk,
            'status': AttendanceRecord.Status.LATE,
            'notes': 'Arrived after the lecture started.',
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['student'], self.student.student_profile.pk)
        self.assertEqual(response.data['recorded_by'], self.teacher.pk)

        duplicate = self.client.post(url, {
            'attendance_session': attendance_session.pk,
            'course_enrollment': self.enrollment.pk,
            'status': AttendanceRecord.Status.PRESENT,
        })
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_closed_session_blocks_changes_and_cannot_reopen(self):
        attendance_session = AttendanceSession.objects.create(
            subject=self.subject,
            academic_session=self.academic_session,
            date=date(2026, 11, 10),
            starts_at=time(9, 0),
            created_by=self.teacher,
        )
        self.client.force_authenticate(self.teacher)
        detail_url = reverse('api_attendance_session_detail', args=[attendance_session.pk])
        response = self.client.patch(detail_url, {'status': AttendanceSession.Status.CLOSED})
        self.assertEqual(response.status_code, 200, response.data)

        response = self.client.post(reverse('api_attendance_records'), {
            'attendance_session': attendance_session.pk,
            'course_enrollment': self.enrollment.pk,
            'status': AttendanceRecord.Status.PRESENT,
        })
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(detail_url, {'status': AttendanceSession.Status.OPEN})
        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.data)

    def test_student_reads_only_own_attendance_and_cannot_write(self):
        first_session = AttendanceSession.objects.create(
            subject=self.subject,
            academic_session=self.academic_session,
            date=date(2026, 11, 10),
            starts_at=time(9, 0),
            created_by=self.teacher,
        )
        second_session = AttendanceSession.objects.create(
            subject=self.other_subject,
            academic_session=self.academic_session,
            date=date(2026, 11, 10),
            starts_at=time(11, 0),
            created_by=self.other_teacher,
        )
        own_record = AttendanceRecord.objects.create(
            attendance_session=first_session,
            course_enrollment=self.enrollment,
            status=AttendanceRecord.Status.PRESENT,
            recorded_by=self.teacher,
        )
        AttendanceRecord.objects.create(
            attendance_session=second_session,
            course_enrollment=self.other_enrollment,
            status=AttendanceRecord.Status.ABSENT,
            recorded_by=self.other_teacher,
        )

        self.client.force_authenticate(self.student)
        response = self.client.get(reverse('api_attendance_records'))
        self.assertEqual([item['id'] for item in response.data], [own_record.pk])
        response = self.client.get(reverse('api_attendance_sessions'))
        self.assertEqual([item['id'] for item in response.data], [first_session.pk])
        response = self.client.post(reverse('api_attendance_records'), {
            'attendance_session': first_session.pk,
            'course_enrollment': self.enrollment.pk,
            'status': AttendanceRecord.Status.PRESENT,
        })
        self.assertEqual(response.status_code, 403)

    def test_admin_deletes_do_not_break_enrollment_history(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(reverse('api_admin_student_detail', args=[self.student.student_profile.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('enrollment history', response.data['error'])

        response = self.client.delete(reverse('api_admin_subject_detail', args=[self.subject.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('enrollment or attendance history', response.data['error'])

        response = self.client.delete(reverse('api_admin_session_detail', args=[self.academic_session.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('enrollment', response.data['error'])
