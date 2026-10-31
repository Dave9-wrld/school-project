from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """Custom creation form for User in Django Admin so role and details can be specified on creation."""
    role = forms.ChoiceField(choices=User.Role.choices, required=True, initial=User.Role.STUDENT)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data.get('role', User.Role.STUDENT)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """Custom change form for User in Django Admin."""
    class Meta:
        model = User
        fields = '__all__'
