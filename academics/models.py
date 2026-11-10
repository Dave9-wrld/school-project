from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Create your models here.

class AcademicSession(models.Model):
    session = models.CharField(max_length=20, unique=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['is_current'], condition=models.Q(is_current=True), name='one_current_academic_session'),
        ]

    def __str__(self):
        return self.session

class ClassRoom(models.Model):
    name = models.CharField(max_length=20, unique=True)
    class_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,   blank=True, limit_choices_to={'role': 'TEACHER'}, related_name='assigned_classes')

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'role': 'TEACHER'}, related_name='subjects_taught')

    def __str__(self):
        return f"{self.name} ({self.code})"

class Grade(models.Model):
  student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='grades')
  subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grades')
  session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='grades')
  continuous_assessment_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0), MaxValueValidator(40)])
  exam_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0), MaxValueValidator(60)])

  class Meta:
    unique_together = ('student', 'subject', 'session')
    constraints = [
        models.CheckConstraint(condition=models.Q(continuous_assessment_score__gte=0, continuous_assessment_score__lte=40), name='grade_ca_between_0_and_40'),
        models.CheckConstraint(condition=models.Q(exam_score__gte=0, exam_score__lte=60), name='grade_exam_between_0_and_60'),
    ]

  def total_score(self):  
    return self.continuous_assessment_score + self.exam_score

  def __str__(self):
    return f"{self.student} - {self.subject}: {self.total_score()}"


class CourseEnrollment(models.Model):
  class Status(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

  student = models.ForeignKey('accounts.StudentProfile', on_delete=models.PROTECT, related_name='course_enrollments')
  subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='course_enrollments')
  session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='course_enrollments')
  status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
  enrolled_on = models.DateField(default=timezone.localdate, null=True, blank=True)
  ended_on = models.DateField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-session__session', 'subject__code', 'student__user__username']
    constraints = [
      models.UniqueConstraint(fields=['student', 'subject', 'session'], name='unique_student_course_session'),
      models.CheckConstraint(
        condition=models.Q(ended_on__isnull=True) | models.Q(enrolled_on__isnull=True) | models.Q(ended_on__gte=models.F('enrolled_on')),
        name='course_enrollment_dates_ordered',
      ),
    ]

  def __str__(self):
    return f"{self.student} - {self.subject} ({self.session})"


class AttendanceSession(models.Model):
  class Status(models.TextChoices):
    OPEN = 'OPEN', 'Open'
    CLOSED = 'CLOSED', 'Closed'

  subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='attendance_sessions')
  academic_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='attendance_sessions')
  date = models.DateField()
  starts_at = models.TimeField()
  ends_at = models.TimeField(null=True, blank=True)
  status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
  created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_attendance_sessions')
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    ordering = ['-date', '-starts_at', 'subject__code']
    constraints = [
      models.UniqueConstraint(fields=['subject', 'academic_session', 'date', 'starts_at'], name='unique_course_attendance_session'),
      models.CheckConstraint(
        condition=models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=models.F('starts_at')),
        name='attendance_session_times_ordered',
      ),
    ]

  def __str__(self):
    return f"{self.subject.code} - {self.date} {self.starts_at}"


class AttendanceRecord(models.Model):
  class Status(models.TextChoices):
    PRESENT = 'PRESENT', 'Present'
    ABSENT = 'ABSENT', 'Absent'
    LATE = 'LATE', 'Late'
    EXCUSED = 'EXCUSED', 'Excused'

  attendance_session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name='records')
  course_enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.PROTECT, related_name='attendance_records')
  status = models.CharField(max_length=8, choices=Status.choices)
  notes = models.TextField(blank=True, max_length=1000)
  recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_attendance')
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    ordering = ['-attendance_session__date', '-attendance_session__starts_at', 'course_enrollment__student__user__username']
    constraints = [
      models.UniqueConstraint(fields=['attendance_session', 'course_enrollment'], name='unique_student_attendance_record'),
    ]

  def __str__(self):
    return f"{self.course_enrollment.student} - {self.attendance_session}: {self.status}"

