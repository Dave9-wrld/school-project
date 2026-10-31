from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from accounts.models import User, StudentProfile, TeacherProfile
from academics.models import ClassRoom, Subject, Grade


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
    
    class Meta:
        model = Grade
        fields = ['id', 'student', 'subject', 'student_name', 'subject_name', 'session', 'session_name', 'continous_assessment_score', 'exam_score', 'total_score']

    def get_total_score(self, obj):
        return obj.total_score()

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.username


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
