from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from accounts.models import User, StudentProfile, TeacherProfile
from academics.models import AcademicSession, AttendanceRecord, AttendanceSession, ClassRoom, CourseEnrollment, Subject, Grade


class AccountCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096, style={'input_type': 'password'})
    admission_number = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20,
        validators=[UniqueValidator(queryset=StudentProfile.objects.all(), message='This admission number is already assigned.')])
    employee_id = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20,
        validators=[UniqueValidator(queryset=TeacherProfile.objects.all(), message='This employee ID is already assigned.')])
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.STUDENT)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name', 'role', 'admission_number', 'employee_id']
        read_only_fields = ['id']

    def validate(self, attrs):
        role = attrs.get('role', User.Role.STUDENT)
        if role != User.Role.STUDENT and attrs.get('admission_number'):
            raise serializers.ValidationError({'admission_number': 'Admission numbers belong to student accounts.'})
        if role != User.Role.TEACHER and attrs.get('employee_id'):
            raise serializers.ValidationError({'employee_id': 'Employee IDs belong to lecturer accounts created by an administrator.'})
        user = User(**{key: value for key, value in attrs.items() if key not in ('password', 'admission_number', 'employee_id')})
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        admission_number = validated_data.pop('admission_number', '') or None
        employee_id = validated_data.pop('employee_id', '') or None
        role = validated_data.pop('role', User.Role.STUDENT)
        try:
            with transaction.atomic():
                user = User.objects.create_user(**validated_data, role=role)
                if role == User.Role.STUDENT:
                    profile, _ = StudentProfile.objects.get_or_create(user=user)
                    profile.admission_number = admission_number
                    profile.save(update_fields=['admission_number'])
                    user.student_profile = profile
                elif role == User.Role.TEACHER:
                    profile, _ = TeacherProfile.objects.get_or_create(user=user)
                    profile.employee_id = employee_id
                    profile.save(update_fields=['employee_id'])
                    user.teacher_profile = profile
                elif role == User.Role.ADMIN:
                    user.is_staff = True
                    user.save(update_fields=['is_staff'])
                return user
        except IntegrityError as exc:
            # Uniqueness can change between validation and insertion.
            if admission_number and StudentProfile.objects.filter(admission_number=admission_number).exists():
                raise serializers.ValidationError({'admission_number': 'This admission number is already assigned.'}) from exc
            if employee_id and TeacherProfile.objects.filter(employee_id=employee_id).exists():
                raise serializers.ValidationError({'employee_id': 'This employee ID is already assigned.'}) from exc
            if User.objects.filter(username=validated_data['username']).exists():
                raise serializers.ValidationError({'username': 'This username is already taken.'}) from exc
            raise


class RegisterSerializer(AccountCreateSerializer):
    # Public signup always creates students, even if a role is supplied.
    role = serializers.CharField(read_only=True)


class UserSerializer(serializers.ModelSerializer):
    admission_number = serializers.CharField(source='student_profile.admission_number', read_only=True, default=None)
    employee_id = serializers.CharField(source='teacher_profile.employee_id', read_only=True, default=None)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'admission_number', 'employee_id']
        read_only_fields = fields


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class_name = serializers.StringRelatedField(source='current_class.name', read_only=True)

    class Meta:
        model = StudentProfile
        fields = ['id', 'user', 'class_name', 'admission_number', 'date_of_birth']

class SubjectSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.username', read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'teacher_name', 'teacher']

class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    session_name = serializers.CharField(source='session.session', read_only=True)
    total_score = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = ['id', 'student', 'subject', 'student_name', 'subject_name', 'session', 'session_name', 'continuous_assessment_score', 'exam_score', 'total_score']

    def get_total_score(self, obj):
        return obj.total_score()

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.username


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    session_name = serializers.CharField(source='session.session', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = CourseEnrollment
        fields = [
            'id', 'student', 'student_name', 'admission_number', 'subject', 'subject_name',
            'subject_code', 'session', 'session_name', 'teacher_name', 'status',
            'enrolled_on', 'ended_on', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_student_name(self, enrollment):
        return enrollment.student.user.get_full_name() or enrollment.student.user.username

    def get_teacher_name(self, enrollment):
        teacher = enrollment.subject.teacher
        return (teacher.get_full_name() or teacher.username) if teacher else None

    def validate(self, attrs):
        student = attrs.get('student', getattr(self.instance, 'student', None))
        status_value = attrs.get('status', getattr(self.instance, 'status', CourseEnrollment.Status.ACTIVE))
        enrolled_on = attrs.get('enrolled_on', getattr(self.instance, 'enrolled_on', None))
        ended_on = attrs.get('ended_on', getattr(self.instance, 'ended_on', None))

        if self.instance:
            for field in ('student', 'subject', 'session'):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: 'Enrollment relationships cannot change after creation.'})
        if student and (student.user.role != User.Role.STUDENT or not student.user.is_active):
            raise serializers.ValidationError({'student': 'Course enrollment requires an active student account.'})
        if enrolled_on and ended_on and ended_on < enrolled_on:
            raise serializers.ValidationError({'ended_on': 'The end date cannot precede the enrollment date.'})
        if status_value == CourseEnrollment.Status.ACTIVE and ended_on:
            raise serializers.ValidationError({'ended_on': 'An active enrollment cannot have an end date.'})
        return attrs


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    session_name = serializers.CharField(source='academic_session.session', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    record_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'subject', 'subject_name', 'subject_code', 'academic_session', 'session_name',
            'teacher_name', 'date', 'starts_at', 'ends_at', 'status', 'record_count',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_teacher_name(self, attendance_session):
        teacher = attendance_session.subject.teacher
        return (teacher.get_full_name() or teacher.username) if teacher else None

    def validate(self, attrs):
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        next_status = attrs.get('status', getattr(self.instance, 'status', AttendanceSession.Status.OPEN))
        request = self.context.get('request')

        if self.instance:
            for field in ('subject', 'academic_session'):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: 'Attendance session relationships cannot change.'})
            if self.instance.status == AttendanceSession.Status.CLOSED and next_status == AttendanceSession.Status.OPEN:
                raise serializers.ValidationError({'status': 'A closed attendance session cannot be reopened.'})
            if self.instance.records.exists():
                for field in ('date', 'starts_at', 'ends_at'):
                    if field in attrs and attrs[field] != getattr(self.instance, field):
                        raise serializers.ValidationError({field: 'Session timing cannot change after attendance is recorded.'})
        if request and request.user.is_teacher() and subject.teacher_id != request.user.pk:
            raise serializers.ValidationError({'subject': 'You can only manage attendance for courses assigned to you.'})
        if ends_at and starts_at and ends_at <= starts_at:
            raise serializers.ValidationError({'ends_at': 'The end time must be later than the start time.'})
        return attrs


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source='course_enrollment.student_id', read_only=True)
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(source='course_enrollment.student.admission_number', read_only=True)
    subject_code = serializers.CharField(source='attendance_session.subject.code', read_only=True)
    subject_name = serializers.CharField(source='attendance_session.subject.name', read_only=True)
    session_date = serializers.DateField(source='attendance_session.date', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'attendance_session', 'course_enrollment', 'student', 'student_name',
            'admission_number', 'subject_code', 'subject_name', 'session_date', 'status',
            'notes', 'recorded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at', 'updated_at']

    def get_student_name(self, record):
        user = record.course_enrollment.student.user
        return user.get_full_name() or user.username

    def validate(self, attrs):
        attendance_session = attrs.get('attendance_session', getattr(self.instance, 'attendance_session', None))
        enrollment = attrs.get('course_enrollment', getattr(self.instance, 'course_enrollment', None))
        request = self.context.get('request')

        if self.instance:
            for field in ('attendance_session', 'course_enrollment'):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: 'Attendance record relationships cannot change.'})
        if attendance_session.status != AttendanceSession.Status.OPEN:
            raise serializers.ValidationError({'attendance_session': 'Attendance can only change while the session is open.'})
        if enrollment.status != CourseEnrollment.Status.ACTIVE:
            raise serializers.ValidationError({'course_enrollment': 'Attendance requires an active course enrollment.'})
        if enrollment.subject_id != attendance_session.subject_id or enrollment.session_id != attendance_session.academic_session_id:
            raise serializers.ValidationError({'course_enrollment': 'The student is not enrolled in this course and academic session.'})
        if request and request.user.is_teacher() and attendance_session.subject.teacher_id != request.user.pk:
            raise serializers.ValidationError({'attendance_session': 'You can only manage attendance for courses assigned to you.'})
        return attrs


class AdminClassSerializer(serializers.ModelSerializer):
    class_teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.TEACHER, is_active=True),
        required=False,
        allow_null=True,
    )
    teacher_name = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClassRoom
        fields = ['id', 'name', 'class_teacher', 'teacher_name', 'student_count']

    def get_teacher_name(self, classroom):
        if not classroom.class_teacher:
            return None
        return classroom.class_teacher.get_full_name() or classroom.class_teacher.username


class StudentClassAssignmentSerializer(serializers.Serializer):
    current_class = serializers.PrimaryKeyRelatedField(
        queryset=ClassRoom.objects.all(),
        allow_null=True,
    )

