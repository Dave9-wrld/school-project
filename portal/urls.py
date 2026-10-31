from django.urls import path

from portal import api_views
from . import views
from .password_reset import PasswordResetRequestAPIView, PasswordResetConfirmAPIView


urlpatterns = [
    path('api/', api_views.APIRootView.as_view(), name='api_root'),
    path('redirect/', views.role_redirect_view, name='role_redirect'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('grades/record/<int:subject_id>/', views.record_grade, name='record_grade'),
    path('api/login/', api_views.CustomAuthToken.as_view(), name='api_login'),
    path('api/logout/', api_views.LogoutAPIView.as_view(), name='api_logout'),
    path('api/register/', api_views.RegisterAPIView.as_view(), name='api_register'),
    path('api/admin/users/', api_views.AdminCreateUserAPIView.as_view(), name='api_admin_users'),
    path('api/password-reset/', PasswordResetRequestAPIView.as_view(), name='api_password_reset'),
    path('api/password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='api_password_reset_confirm'),
    path('api/admin/stats/', api_views.AdminStatsAPIView.as_view(), name='api_admin_stats'),
    path('api/admin/classes/', api_views.AdminClassesAPIView.as_view(), name='api_admin_classes'),
    path('api/admin/classes/<int:class_id>/', api_views.AdminClassDetailAPIView.as_view(), name='api_admin_class_detail'),
    path('api/admin/students/', api_views.AdminStudentsAPIView.as_view(), name='api_admin_students'),
    path('api/admin/students/<int:student_id>/', api_views.AdminStudentDetailAPIView.as_view(), name='api_admin_student_detail'),
    path('api/admin/students/<int:student_id>/class/', api_views.AdminStudentClassAPIView.as_view(), name='api_admin_student_class'),
    path('api/admin/teachers/', api_views.AdminTeachersAPIView.as_view(), name='api_admin_teachers'),
    path('api/admin/teachers/<int:teacher_id>/', api_views.AdminTeacherDetailAPIView.as_view(), name='api_admin_teacher_detail'),
    path('api/admin/subjects/', api_views.AdminSubjectsAPIView.as_view(), name='api_admin_subjects'),
    path('api/admin/subjects/<int:subject_id>/', api_views.AdminSubjectDetailAPIView.as_view(), name='api_admin_subject_detail'),
    path('api/admin/sessions/', api_views.AdminSessionsAPIView.as_view(), name='api_admin_sessions'),
    path('api/admin/sessions/<int:session_id>/', api_views.AdminSessionDetailAPIView.as_view(), name='api_admin_session_detail'),
    path('api/admin/grades/', api_views.AdminGradesAPIView.as_view(), name='api_admin_grades'),
    path('api/admin/grades/<int:grade_id>/', api_views.AdminGradeDetailAPIView.as_view(), name='api_admin_grade_detail'),
    path('api/teacher/subjects/', api_views.TeacherSubjectsAPIView.as_view(), name='api_teacher_subjects'),
    path('api/teacher/students/', api_views.TeacherStudentsAPIView.as_view(), name='api_teacher_students'),
    path('api/teacher/classes/', api_views.TeacherClassesAPIView.as_view(), name='api_teacher_classes'),
    path('api/teacher/grades/', api_views.TeacherGradesAPIView.as_view(), name='api_teacher_grades_list'),
    path('api/teacher/grades/record/<int:subject_id>/', api_views.RecordGradeAPIView.as_view(), name='api_teacher_grades'),
    path('api/student/grades/', api_views.StudentGradesAPIView.as_view(), name='api_students_grade'),
    path('api/student/profile/', api_views.StudentProfileAPIView.as_view(), name='api_student_profile'),
    
]
