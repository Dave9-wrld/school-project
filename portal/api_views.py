from django.contrib.auth import logout
from django.db.models import Count
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

from accounts.models import StudentProfile, User
from academics.models import AcademicSession, ClassRoom, Grade, Subject
from .permissions import IsAdminUserRole, IsStudentUserRole, IsTeacherUserRole
from .serializers import (
    AccountCreateSerializer, UserSerializer, AdminClassSerializer, GradeSerializer, RegisterSerializer,
    StudentClassAssignmentSerializer, SubjectSerializer,
)
from .authentication import token_expires_at
from .throttles import LoginRateThrottle, RegistrationRateThrottle


class APIRootView(APIView):
    """Browse the School API.

    Use Log in at the top right to test with your browser session. Each endpoint
    requires the matching user role. Token clients can POST username and password
    to the login endpoint, then send Authorization: Token <token>.

    The record-grade link uses subject 1 as an example; replace 1 with your
    subject ID. POST student (a StudentProfile ID), continous_assessment_score,
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
        'name': profile.user.get_full_name() or profile.user.username,
        'username': profile.user.username,
        'admission_number': profile.admission_number or '',
        'current_class': profile.current_class_id,
        'current_class_name': profile.current_class.name if profile.current_class else None,
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


class AdminStudentsAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        students = StudentProfile.objects.filter(
            user__role=User.Role.STUDENT, user__is_active=True,
        ).select_related('user', 'current_class').order_by('user__first_name', 'user__last_name', 'user__username')
        return Response([student_class_data(student) for student in students])


class AdminStudentClassAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def patch(self, request, student_id):
        student = get_object_or_404(
            StudentProfile.objects.select_related('user', 'current_class'),
            pk=student_id, user__role=User.Role.STUDENT, user__is_active=True,
        )
        serializer = StudentClassAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student.current_class = serializer.validated_data['current_class']
        student.save(update_fields=['current_class'])
        return Response(student_class_data(student))


class AdminTeachersAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True).select_related('teacher_profile').order_by('first_name', 'last_name', 'username')
        return Response([
            {'id': teacher.pk, 'name': teacher.get_full_name() or teacher.username, 'username': teacher.username,
             'employee_id': getattr(getattr(teacher, 'teacher_profile', None), 'employee_id', None) or ''}
            for teacher in teachers
        ])


class TeacherSubjectsAPIView(APIView):
    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        subjects = Subject.objects.filter(teacher=request.user)
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data)


class TeacherStudentsAPIView(APIView):
    """Minimal student choices for lecturers who can record grades."""

    permission_classes = [IsTeacherUserRole]

    def get(self, request):
        if not Subject.objects.filter(teacher=request.user).exists():
            return Response([])
        students = StudentProfile.objects.filter(
            user__role=User.Role.STUDENT, user__is_active=True,
        ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__username')
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



