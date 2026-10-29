from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'School Admin'
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'

    role = models.CharField(max_length=15, choices=Role.choices, default=Role.STUDENT)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def is_teacher(self):
        return self.role == self.Role.TEACHER

    def is_student(self):
        return self.role == self.Role.STUDENT

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
   
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} (Teacher Profile)"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    admission_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    current_class = models.ForeignKey('academics.Classroom', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} (Student Profile)"