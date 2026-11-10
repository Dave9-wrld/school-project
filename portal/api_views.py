from django.contrib.auth import logout
from django.db.models import Count, F, Q
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile, TeacherProfile, User
from academics.models import AcademicSession, AttendanceRecord, AttendanceSession, ClassRoom, CourseEnrollment, Grade, Subject
from .permissions import AttendancePermission, CourseEnrollmentPermission, IsAdminUserRole, IsStudentUserRole, IsTeacherUserRole
from .serializers import (
    AccountCreateSerializer, AttendanceRecordSerializer, AttendanceSessionSerializer,
    CourseEnrollmentSerializer, UserSerializer, AdminClassSerializer, GradeSerializer,
    RegisterSerializer, StudentClassAssignmentSerializer, SubjectSerializer,
)
from .authentication import token_expires_at
from .throttles import LoginRateThrottle, RegistrationRateThrottle


class APIRootView(APIView):
    """Browse the School API.

    Use Log in at the top right to test with your browser session. Each endpoint
    requires the matching user role. Token clients can POST username and password
    to the login endpoint, then send Authorization: Token <token>.

    The record-grade link uses subject 1 as an example; replace 1 with your
    subject ID. POST student (a StudentProfile ID), continuous_assessment_score,
    and exam_score. A current academic session and an assigned teacher are required.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'register': {'method': 'POST', 'url': reverse('api_register', request=request)},
            'login': {'method': 'POST', 'url': reverse('api_login', request=request)},
            'password_reset': {'method': 'POST', 'url': reverse('api_password_reset', request=request)},
            'password_reset_confirm': {'method': 'POST', 'url': reverse('api_password_reset_confirm', request=request)},
            'logout': {'method': 'POST', 'url': reverse('api_logout', request=request)},
            'admin_stats': {'method': 'GET', 'url': reverse('api_admin_stats', request=request)},
            'admin_users': {'method': 'POST', 'url': reverse('api_admin_users', request=request)},
            'admin_classes': {'method': 'GET, POST', 'url': reverse('api_admin_classes', request=request)},
            'admin_class_example_1': {'method': 'PATCH', 'url': reverse('api_admin_class_detail', kwargs={'class_id': 1}, request=request)},
            'admin_students': {'method': 'GET', 'url': reverse('api_admin_students', request=request)},
            'admin_student_class_example_1': {'method': 'PATCH', 'url': reverse('api_admin_student_class', kwargs={'student_id': 1}, request=request)},
            'admin_teachers': {'method': 'GET', 'url': reverse('api_admin_teachers', request=request)},
            'teacher_subjects': {'method': 'GET', 'url': reverse('api_teacher_subjects', request=request)},
            'teacher_students': {'method': 'GET', 'url': reverse('api_teacher_students', request=request)},
            'teacher_classes': {'method': 'GET', 'url': reverse('api_teacher_classes', request=request)},
            'teacher_grades': {'method': 'GET', 'url': reverse('api_teacher_grades_list', request=request)},
            'record_grade_example_subject_1': {
                'method': 'POST',
                'url': reverse('api_teacher_grades', kwargs={'subject_id': 1}, request=request),
            },
            'student_grades': {'method': 'GET', 'url': reverse('api_students_grade', request=request)},
            'student_profile': {'method': 'GET', 'url': reverse('api_student_profile', request=request)},
            'course_enrollments': {'method': 'GET, POST (admin)', 'url': reverse('api_course_enrollments', request=request)},
            'attendance_sessions': {'method': 'GET, POST (admin/teacher)', 'url': reverse('api_attendance_sessions', request=request)},
            'attendance_records': {'method': 'GET, POST (admin/teacher)', 'url': reverse('api_attendance_records', request=request)},
        })


class RegisterAPIView(CreateAPIView):
    """Public student signup; the frontend still directs new users to login."""
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [RegistrationRateThrottle]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'message': 'User registered successfully.',
            'token': token.key,
            'expires_at': token_expires_at(token).isoformat(),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class AdminCreateUserAPIView(CreateAPIView):
    """Administrators provision student/lecturer accounts, not public signups."""
    permission_classes = [IsAdminUserRole]
    serializer_class = AccountCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class CustomAuthToken(ObtainAuthToken):
    """Generate an auth token and return user details and role."""

    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            token, _ = Token.objects.get_or_create(user=user)
            if timezone.now() >= token_expires_at(token):
                token.delete()
                token = Token.objects.create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'display_name': user.get_full_name() or user.username,
            'role': user.role,
            'expires_at': token_expires_at(token).isoformat(),
        })


class LogoutAPIView(APIView):
    """Revoke the current user's API token and end their browser session."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


def scoped_course_enrollments(user):
    queryset = CourseEnrollment.objects.select_related(
        'student__user', 'subject__teacher', 'session',
    )
    if user.is_admin():
        return queryset
    if user.is_teacher():
        return queryset.filter(subject__teacher=user)
    return queryset.filter(student__user=user)


def scoped_attendance_sessions(user):
    queryset = AttendanceSession.objects.select_related(
        'subject__teacher', 'academic_session', 'created_by',
    ).annotate(record_count=Count('records'))
    if user.is_admin():
        return queryset
    if user.is_teacher():
        return queryset.filter(subject__teacher=user)
    return queryset.filter(
        subject__course_enrollments__student__user=user,
        subject__course_enrollments__session=F('academic_session'),
    ).distinct()


def scoped_attendance_records(user):
    queryset = AttendanceRecord.objects.select_related(
        'attendance_session__subject', 'attendance_session__academic_session',
        'course_enrollment__student__user', 'recorded_by',
    )
    if user.is_admin():
        return queryset
    if user.is_teacher():
        return queryset.filter(attendance_session__subject__teacher=user)
    return queryset.filter(course_enrollment__student__user=user)


class CourseEnrollmentListCreateAPIView(APIView):
    permission_classes = [CourseEnrollmentPermission]

    def get(self, request):
        queryset = scoped_course_enrollments(request.user)
        for parameter, field in (
            ('student', 'student_id'), ('subject', 'subject_id'), ('session', 'session_id'), ('status', 'status'),
        ):
            value = request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field: value})
        return Response(CourseEnrollmentSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = CourseEnrollmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CourseEnrollmentDetailAPIView(APIView):
    permission_classes = [CourseEnrollmentPermission]

    def patch(self, request, enrollment_id):
        enrollment = get_object_or_404(scoped_course_enrollments(request.user), pk=enrollment_id)
        serializer = CourseEnrollmentSerializer(enrollment, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AttendanceSessionListCreateAPIView(APIView):
    permission_classes = [AttendancePermission]

    def get(self, request):
        queryset = scoped_attendance_sessions(request.user)
        for parameter, field in (
            ('subject', 'subject_id'), ('academic_session', 'academic_session_id'), ('status', 'status'),
        ):
            value = request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field: value})
        return Response(AttendanceSessionSerializer(queryset, many=True).data)

    def post(self, request):
        data = request.data.copy()
        if not data.get('academic_session'):
            current_session = AcademicSession.objects.filter(is_current=True).first()
            if not current_session:
                return Response(
                    {'academic_session': 'No current academic session is configured.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data['academic_session'] = current_session.pk
        serializer = AttendanceSessionSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        attendance_session = serializer.save(created_by=request.user)
        attendance_session.record_count = 0
        return Response(AttendanceSessionSerializer(attendance_session).data, status=status.HTTP_201_CREATED)


class AttendanceSessionDetailAPIView(APIView):
    permission_classes = [AttendancePermission]

    def patch(self, request, attendance_session_id):
        attendance_session = get_object_or_404(scoped_attendance_sessions(request.user), pk=attendance_session_id)
        serializer = AttendanceSessionSerializer(
            attendance_session, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AttendanceRecordListCreateAPIView(APIView):
    permission_classes = [AttendancePermission]

    def get(self, request):
        queryset = scoped_attendance_records(request.user)
        for parameter, field in (
            ('attendance_session', 'attendance_session_id'),
            ('course_enrollment', 'course_enrollment_id'),
            ('status', 'status'),
        ):
            value = request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field: value})
        return Response(AttendanceRecordSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = AttendanceRecordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(recorded_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttendanceRecordDetailAPIView(APIView):
    permission_classes = [AttendancePermission]

    def patch(self, request, attendance_record_id):
        attendance_record = get_object_or_404(scoped_attendance_records(request.user), pk=attendance_record_id)
        serializer = AttendanceRecordSerializer(
            attendance_record, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(recorded_by=request.user)
        return Response(serializer.data)


class AdminStatsAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        return Response({
            'total_teachers': User.objects.filter(role=User.Role.TEACHER).count(),
            'total_students': User.objects.filter(role=User.Role.STUDENT).count(),
            'total_subjects': Subject.objects.count(),
        })


def student_class_data(profile):
    return {
        'id': profile.pk,
        'user_id': profile.user.pk,
        'name': profile.user.get_full_name() or profile.user.username,
        'first_name': profile.user.first_name,
        'last_name': profile.user.last_name,
        'username': profile.user.username,
        'email': profile.user.email,
        'phone_number': profile.user.phone_number or '',
        'admission_number': profile.admission_number or '',
        'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
        'current_class': profile.current_class_id,
        'current_class_name': profile.current_class.name if profile.current_class else None,
        'is_active': profile.user.is_active,
    }


def teacher_data(teacher):
    profile = getattr(teacher, 'teacher_profile', None)
    return {
        'id': teacher.pk,
        'name': teacher.get_full_name() or teacher.username,
        'first_name': teacher.first_name,
        'last_name': teacher.last_name,
        'username': teacher.username,
        'email': teacher.email,
        'phone_number': teacher.phone_number or '',
        'employee_id': getattr(profile, 'employee_id', None) or '',
        'department': getattr(profile, 'department', None) or '',
        'is_active': teacher.is_active,
        'assigned_classes': list(teacher.assigned_classes.values_list('name', flat=True)),
        'assigned_subjects': list(teacher.subjects_taught.values_list('name', flat=True)),
    }


class AdminClassesAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        classes = ClassRoom.objects.select_related('class_teacher').annotate(
            student_count=Count('students'),
        ).order_by('name')
        return Response(AdminClassSerializer(classes, many=True).data)

    def post(self, request):
        serializer = AdminClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        classroom = serializer.save()
        classroom.student_count = 0
        return Response(AdminClassSerializer(classroom).data, status=status.HTTP_201_CREATED)


class AdminClassDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, class_id):
        classroom = get_object_or_404(ClassRoom.objects.select_related('class_teacher'), pk=class_id)
        serializer = AdminClassSerializer(classroom, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        classroom.student_count = classroom.students.count()
        return Response(AdminClassSerializer(classroom).data)

    def delete(self, request, class_id):
        classroom = get_object_or_404(ClassRoom, pk=class_id)
        classroom.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminStudentsAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        students = StudentProfile.objects.filter(
            user__role=User.Role.STUDENT,
        ).select_related('user', 'current_class').order_by('user__first_name', 'user__last_name', 'user__username')
        return Response([student_class_data(student) for student in students])


class AdminStudentDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, student_id):
        student = get_object_or_404(
            StudentProfile.objects.select_related('user', 'current_class'),
            pk=student_id, user__role=User.Role.STUDENT,
        )
        data = request.data
        user = student.user
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])
        user.save()

        if 'admission_number' in data:
            adm_no = str(data['admission_number']).strip() or None
            if adm_no and StudentProfile.objects.exclude(pk=student.pk).filter(admission_number=adm_no).exists():
                return Response({'admission_number': 'This admission number is already assigned.'}, status=status.HTTP_400_BAD_REQUEST)
            student.admission_number = adm_no
        if 'current_class' in data:
            class_id = data['current_class']
            if class_id:
                classroom = get_object_or_404(ClassRoom, pk=class_id)
                student.current_class = classroom
            else:
                student.current_class = None
        if 'date_of_birth' in data:
            dob = data['date_of_birth'] or None
            student.date_of_birth = dob
        student.save()
        student.refresh_from_db()
        return Response(student_class_data(student))

    def delete(self, request, student_id):
        student = get_object_or_404(StudentProfile, pk=student_id)
        if student.course_enrollments.exists():
            return Response(
                {'error': 'Cannot delete a student with course enrollment history. Deactivate the account instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = student.user
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminStudentClassAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, student_id):
        student = get_object_or_404(
            StudentProfile.objects.select_related('user', 'current_class'),
            pk=student_id, user__role=User.Role.STUDENT,
        )
        serializer = StudentClassAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student.current_class = serializer.validated_data['current_class']
        student.save(update_fields=['current_class'])
        return Response(student_class_data(student))


class AdminTeachersAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        teachers = User.objects.filter(role=User.Role.TEACHER).select_related('teacher_profile').prefetch_related('assigned_classes', 'subjects_taught').order_by('first_name', 'last_name', 'username')
        return Response([teacher_data(teacher) for teacher in teachers])


class AdminTeacherDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, teacher_id):
        teacher = get_object_or_404(User.objects.select_related('teacher_profile'), pk=teacher_id, role=User.Role.TEACHER)
        data = request.data
        if 'first_name' in data:
            teacher.first_name = data['first_name']
        if 'last_name' in data:
            teacher.last_name = data['last_name']
        if 'email' in data:
            teacher.email = data['email']
        if 'phone_number' in data:
            teacher.phone_number = data['phone_number']
        if 'is_active' in data:
            teacher.is_active = bool(data['is_active'])
        teacher.save()
        profile, _ = TeacherProfile.objects.get_or_create(user=teacher)
        if 'employee_id' in data:
            emp_id = str(data['employee_id']).strip() or None
            if emp_id and TeacherProfile.objects.exclude(pk=profile.pk).filter(employee_id=emp_id).exists():
                return Response({'employee_id': 'This employee ID is already assigned.'}, status=status.HTTP_400_BAD_REQUEST)
            profile.employee_id = emp_id
        if 'department' in data:
            profile.department = str(data['department']).strip() or None
        profile.save()
        teacher = User.objects.select_related('teacher_profile').get(pk=teacher.pk)
        return Response(teacher_data(teacher))

    def delete(self, request, teacher_id):
        teacher = get_object_or_404(User, pk=teacher_id, role=User.Role.TEACHER)
        teacher.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminSubjectsAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        subjects = Subject.objects.select_related('teacher').annotate(
            grades_count=Count('grades'),
        ).order_by('code')
        result = []
        for s in subjects:
            result.append({
                'id': s.pk,
                'name': s.name,
                'code': s.code,
                'teacher': s.teacher_id,
                'teacher_name': (s.teacher.get_full_name() or s.teacher.username) if s.teacher else None,
                'grades_count': s.grades_count,
            })
        return Response(result)

    def post(self, request):
        name = request.data.get('name', '').strip()
        code = request.data.get('code', '').strip().upper()
        teacher_id = request.data.get('teacher')
        if not name or not code:
            return Response({'error': 'Subject name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if Subject.objects.filter(name__iexact=name).exists():
            return Response({'name': 'A course with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        if Subject.objects.filter(code__iexact=code).exists():
            return Response({'code': 'A course with this code already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        teacher = None
        if teacher_id:
            teacher = get_object_or_404(User, pk=teacher_id, role=User.Role.TEACHER)
        subject = Subject.objects.create(name=name, code=code, teacher=teacher)
        return Response({
            'id': subject.pk,
            'name': subject.name,
            'code': subject.code,
            'teacher': subject.teacher_id,
            'teacher_name': (teacher.get_full_name() or teacher.username) if teacher else None,
            'grades_count': 0,
        }, status=status.HTTP_201_CREATED)


class AdminSubjectDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, subject_id):
        subject = get_object_or_404(Subject.objects.select_related('teacher'), pk=subject_id)
        name = request.data.get('name', '').strip()
        code = request.data.get('code', '').strip().upper()
        if name and name.lower() != subject.name.lower():
            if Subject.objects.exclude(pk=subject.pk).filter(name__iexact=name).exists():
                return Response({'name': 'A course with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            subject.name = name
        elif name:
            subject.name = name
        if code and code.lower() != subject.code.lower():
            if Subject.objects.exclude(pk=subject.pk).filter(code__iexact=code).exists():
                return Response({'code': 'A course with this code already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            subject.code = code
        elif code:
            subject.code = code
        if 'teacher' in request.data:
            teacher_id = request.data.get('teacher')
            if teacher_id:
                subject.teacher = get_object_or_404(User, pk=teacher_id, role=User.Role.TEACHER)
            else:
                subject.teacher = None
        subject.save()
        return Response({
            'id': subject.pk,
            'name': subject.name,
            'code': subject.code,
            'teacher': subject.teacher_id,
            'teacher_name': (subject.teacher.get_full_name() or subject.teacher.username) if subject.teacher else None,
            'grades_count': subject.grades.count(),
        })

    def delete(self, request, subject_id):
        subject = get_object_or_404(Subject, pk=subject_id)
        if subject.course_enrollments.exists() or subject.attendance_sessions.exists():
            return Response(
                {'error': 'Cannot delete a course with enrollment or attendance history.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subject.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminSessionsAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        sessions = AcademicSession.objects.annotate(grades_count=Count('grades')).order_by('-session')
        return Response([
            {
                'id': s.pk,
                'session': s.session,
                'is_current': s.is_current,
                'grades_count': s.grades_count,
            }
            for s in sessions
        ])

    def post(self, request):
        session_name = request.data.get('session', '').strip()
        is_current = bool(request.data.get('is_current', False))
        if not session_name:
            return Response({'session': 'Session name is required (e.g. 2024/2025).'}, status=status.HTTP_400_BAD_REQUEST)
        if AcademicSession.objects.filter(session=session_name).exists():
            return Response({'session': 'This academic session already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if is_current:
                AcademicSession.objects.filter(is_current=True).update(is_current=False)
            acad_session = AcademicSession.objects.create(session=session_name, is_current=is_current)

        return Response({
            'id': acad_session.pk,
            'session': acad_session.session,
            'is_current': acad_session.is_current,
            'grades_count': 0,
        }, status=status.HTTP_201_CREATED)


class AdminSessionDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, session_id):
        acad_session = get_object_or_404(AcademicSession, pk=session_id)
        session_name = request.data.get('session', '').strip()
        if session_name and session_name != acad_session.session:
            if AcademicSession.objects.exclude(pk=acad_session.pk).filter(session=session_name).exists():
                return Response({'session': 'This academic session already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            acad_session.session = session_name

        if 'is_current' in request.data:
            make_current = bool(request.data.get('is_current'))
            with transaction.atomic():
                if make_current:
                    AcademicSession.objects.filter(is_current=True).exclude(pk=acad_session.pk).update(is_current=False)
                    acad_session.is_current = True
                else:
                    acad_session.is_current = False
                acad_session.save()
        else:
            acad_session.save()

        return Response({
            'id': acad_session.pk,
            'session': acad_session.session,
            'is_current': acad_session.is_current,
            'grades_count': acad_session.grades.count(),
        })

    def delete(self, request, session_id):
        acad_session = get_object_or_404(AcademicSession, pk=session_id)
        if (
            acad_session.grades.exists()
            or acad_session.course_enrollments.exists()
            or acad_session.attendance_sessions.exists()
        ):
            return Response(
                {'error': 'Cannot delete an academic session with grade, enrollment, or attendance history.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        acad_session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminGradesAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        queryset = Grade.objects.select_related('student__user', 'subject', 'session').order_by('-pk')
        session_id = request.query_params.get('session')
        subject_id = request.query_params.get('subject')
        search = request.query_params.get('search')
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if search:
            queryset = queryset.filter(
                Q(student__user__first_name__icontains=search) |
                Q(student__user__last_name__icontains=search) |
                Q(student__user__username__icontains=search) |
                Q(student__admission_number__icontains=search) |
                Q(subject__name__icontains=search) |
                Q(subject__code__icontains=search)
            )
        return Response(GradeSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = GradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grade = serializer.save()
        return Response(GradeSerializer(grade).data, status=status.HTTP_201_CREATED)


class AdminGradeDetailAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, grade_id):
        grade = get_object_or_404(Grade, pk=grade_id)
        serializer = GradeSerializer(grade, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GradeSerializer(grade).data)

    def delete(self, request, grade_id):
        grade = get_object_or_404(Grade, pk=grade_id)
        grade.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeacherSubjectsAPIView(APIView):
    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        subjects = Subject.objects.filter(teacher=request.user)
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data)


class TeacherStudentsAPIView(APIView):
    """Active course-enrolled student choices for lecturers."""

    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        students = StudentProfile.objects.filter(
            user__role=User.Role.STUDENT,
            user__is_active=True,
            course_enrollments__subject__teacher=request.user,
            course_enrollments__session__is_current=True,
            course_enrollments__status=CourseEnrollment.Status.ACTIVE,
        ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__username')
        students = students.distinct()
        return Response([
            {
                'id': student.pk,
                'name': student.user.get_full_name() or student.user.username,
                'username': student.user.username,
                'admission_number': student.admission_number or '',
            }
            for student in students
        ])


class TeacherClassesAPIView(APIView):
    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        classes = ClassRoom.objects.filter(class_teacher=request.user).annotate(
            student_count=Count('students'),
        ).order_by('name')
        return Response(AdminClassSerializer(classes, many=True).data)


class TeacherGradesAPIView(APIView):
    """Results for courses currently assigned to this lecturer."""

    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        grades = Grade.objects.filter(subject__teacher=request.user).select_related(
            'student__user', 'subject', 'session',
        ).order_by('-pk')
        return Response(GradeSerializer(grades, many=True).data)


class RecordGradeAPIView(APIView):
    permission_classes = [IsTeacherUserRole]

    def post(self, request, subject_id):
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if not current_session:
            return Response(
                {'error': 'No active academic session found'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Teachers can only grade subjects assigned to them
        if not Subject.objects.filter(pk=subject_id, teacher=request.user).exists():
            return Response(
                {'error': 'Subject not found or not assigned to you'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()
        data['subject'] = subject_id
        data['session'] = current_session.id

        # Validate the student before using its ID in a database lookup.
        try:
            student = GradeSerializer().fields['student'].run_validation(data.get('student'))
        except ValidationError as exc:
            raise ValidationError({'student': exc.detail}) from exc

        if not CourseEnrollment.objects.filter(
            student=student,
            subject_id=subject_id,
            session=current_session,
            status=CourseEnrollment.Status.ACTIVE,
        ).exists():
            return Response(
                {'student': 'This student is not actively enrolled in the course for the current session.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_grade = Grade.objects.filter(
            student=student,
            subject_id=subject_id,
            session=current_session,
        ).first()

        if existing_grade:
            serializer = GradeSerializer(existing_grade, data=data, partial=True)
            success_status = status.HTTP_200_OK
        else:
            serializer = GradeSerializer(data=data)
            success_status = status.HTTP_201_CREATED

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=success_status)


class StudentGradesAPIView(APIView):
    permission_classes = [IsStudentUserRole]

    def get(self, request):
        try:
            profile = request.user.student_profile
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student profile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        grades = Grade.objects.filter(student=profile).select_related('student__user', 'subject', 'session')
        return Response(GradeSerializer(grades, many=True).data)


class StudentProfileAPIView(APIView):
    permission_classes = [IsStudentUserRole]

    def get(self, request):
        profile = get_object_or_404(
            StudentProfile.objects.select_related('user', 'current_class'), user=request.user,
        )
        return Response(student_class_data(profile))
