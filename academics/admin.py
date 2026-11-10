from django.contrib import admin
from .models import AcademicSession, AttendanceRecord, AttendanceSession, ClassRoom, CourseEnrollment, Subject, Grade

# Register your models here.
admin.site.register(AcademicSession)
admin.site.register(ClassRoom)
admin.site.register(Subject)
admin.site.register(CourseEnrollment)
admin.site.register(AttendanceSession)
admin.site.register(AttendanceRecord)

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'session', 'continuous_assessment_score', 'exam_score', 'total_score')
    list_filter = ('session', 'subject')
         
