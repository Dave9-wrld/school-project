from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

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

