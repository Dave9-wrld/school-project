"""Disposable browser QA server. Never reads or writes the real school database."""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school.settings')

from django.conf import settings

with tempfile.TemporaryDirectory(prefix='dave-next-qa-') as directory:
    settings.DATABASES['default']['NAME'] = Path(directory) / 'preview.sqlite3'
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connections
    from accounts.models import User
    from academics.models import AcademicSession, ClassRoom, Grade, Subject

    call_command('migrate', verbosity=0)
    password = 'PortalPreview!73'
    User.objects.create_user(username='qa_admin', password=password, first_name='Alex', last_name='Morgan', role='ADMIN')
    lecturer = User.objects.create_user(username='qa_lecturer', password=password, first_name='Ada', last_name='Okafor', role='TEACHER')
    group = ClassRoom.objects.create(name='Year 1 — Sciences', class_teacher=lecturer)
    ClassRoom.objects.create(name='Year 2 — Humanities')
    session = AcademicSession.objects.create(session='2026/2027', is_current=True)
    courses = [Subject.objects.create(name=name, code=code, teacher=lecturer) for name, code in [('Applied Mathematics', 'MTH 101'), ('Scientific Thinking', 'SCI 102'), ('Academic Writing', 'ENG 103')]]
    for index, (first, last) in enumerate([('Amara', 'Okafor'), ('Bayo', 'Adeyemi'), ('Tomi', 'Bello'), ('Zara', 'Ibrahim')]):
        student = User.objects.create_user(username='qa_student' if index == 0 else f'qa_student_{index}', password=password, first_name=first, last_name=last, role='STUDENT')
        profile = student.student_profile
        profile.current_class = group if index < 3 else None
        profile.admission_number = f'DU/26/00{index + 1}'
        profile.save()
        for number, course in enumerate(courses[:3 if index == 0 else 1]):
            Grade.objects.create(student=profile, subject=course, session=session, continous_assessment_score=28 + number, exam_score=44 + index + number)
    print('Disposable QA backend ready on http://127.0.0.1:8011', flush=True)
    try:
        call_command('runserver', '127.0.0.1:8011', use_reloader=False)
    finally:
        connections.close_all()
