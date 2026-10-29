from django import forms

from academics.models import Grade


class GradeEntryForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['student', 'continous_assessment_score', 'exam_score']
        labels = {
            'continous_assessment_score': 'Continuous assessment (0–40)',
            'exam_score': 'Exam score (0–60)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = self.fields['student'].queryset.filter(
            user__role='STUDENT', user__is_active=True,
        ).select_related('user').order_by('user__username')
