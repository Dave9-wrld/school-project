from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .decorators import role_required
from .forms import GradeEntryForm
from accounts.models import User, TeacherProfile, StudentProfile
from academics.models import ClassRoom, AcademicSession, Subject, Grade

# Create your views here.

@login_required
def role_redirect_view(request):
    '''Direct every uer to their specific dashboard based on their assigned role'''
    if request.user.role == User.Role.ADMIN or request.user.is_superuser:
        return redirect('admin_dashboard')
    elif request.user.role == User.Role.TEACHER:
        return redirect('teacher_dashboard')
    elif request.user.role == User.Role.STUDENT:
        return redirect('student_dashboard')
    else:
        return redirect ('login')


@role_required(allowed_roles=['ADMIN'])
def admin_dashboard(request):
    context = {
        'total_teachers': User.objects.filter(role=User.Role.TEACHER).count(),
        'total_students': User.objects.filter(role=User.Role.STUDENT).count(),
        'total_subjects': Subject.objects.count(),
        'total_classes': ClassRoom.objects.count(),
    }
    return render(request, 'admin_dashboard.html', context)

@role_required(allowed_roles=['TEACHER'])
def teacher_dashboard(request):
    taught_subjects = Subject.objects.filter(teacher=request.user)
    assigned_classes = ClassRoom.objects.filter(class_teacher=request.user)
    context = {
        'taught_subjects': taught_subjects,
        'assigned_classes': assigned_classes,
    }
    return render(request, 'teacher_dashboard.html', context)

@role_required(allowed_roles=['TEACHER'])
@require_http_methods(['GET', 'POST'])
def record_grade(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    current_session = AcademicSession.objects.filter(is_current=True).first()
    form = GradeEntryForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid() and current_session:
        Grade.objects.update_or_create(
            student=form.cleaned_data['student'], subject=subject, session=current_session,
            defaults={
                'continuous_assessment_score': form.cleaned_data['continuous_assessment_score'],
                'exam_score': form.cleaned_data['exam_score'],
            },
        )
        messages.success(request, 'Grade saved successfully.')
        return redirect('teacher_dashboard')
    if request.method == 'POST' and not current_session:
        form.add_error(None, 'No current academic session. Ask an administrator to activate one.')
    return render(request, 'record_grade.html', {
        'subject': subject, 'form': form, 'session': current_session,
    }, status=400 if request.method == 'POST' else 200)
@role_required(allowed_roles=['STUDENT'])
def student_dashboard(request):
    profile = get_object_or_404(StudentProfile, user=request.user)

    grades = Grade.objects.filter(
        student=profile
    ).select_related('subject', 'session')

    context = {
        'profile': profile,
        'grades': grades,
    }

    return render(request, 'student_dashboard.html', context)

