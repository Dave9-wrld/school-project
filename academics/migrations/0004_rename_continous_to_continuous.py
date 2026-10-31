from django.db import migrations


class Migration(migrations.Migration):
    """Rename continous_assessment_score -> continuous_assessment_score (typo fix)."""

    dependencies = [
        ('academics', '0003_alter_grade_continous_assessment_score_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='grade',
            old_name='continous_assessment_score',
            new_name='continuous_assessment_score',
        ),
        # Rename the old check-constraint that used the misspelled field name.
        migrations.RemoveConstraint(
            model_name='grade',
            name='grade_ca_between_0_and_40',
        ),
        migrations.AddConstraint(
            model_name='grade',
            constraint=__import__('django.db.models', fromlist=['Q', 'CheckConstraint']).CheckConstraint(
                condition=__import__('django.db.models', fromlist=['Q']).Q(
                    continuous_assessment_score__gte=0,
                    continuous_assessment_score__lte=40,
                ),
                name='grade_ca_between_0_and_40',
            ),
        ),
    ]
