from django.db import migrations


def backfill_profiles(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    alias = schema_editor.connection.alias
    for role, model_name in [('STUDENT', 'StudentProfile'), ('TEACHER', 'TeacherProfile')]:
        Profile = apps.get_model('accounts', model_name)
        for user_id in User.objects.using(alias).filter(role=role).values_list('pk', flat=True).iterator():
            Profile.objects.using(alias).get_or_create(user_id=user_id)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial'), ('academics', '0002_initial')]
    operations = [migrations.RunPython(backfill_profiles, migrations.RunPython.noop)]
