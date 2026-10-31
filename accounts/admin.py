from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, TeacherProfile, StudentProfile
from .forms import CustomUserCreationForm, CustomUserChangeForm


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    extra = 0


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'first_name',
                'last_name',
                'role',
                'phone_number',
                'password1',
                'password2',
            ),
        }),
    )

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role', 'phone_number')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    def get_inlines(self, request, obj):
        if obj is None:
            return []
        if obj.role == User.Role.TEACHER:
            return [TeacherProfileInline]
        elif obj.role == User.Role.STUDENT:
            return [StudentProfileInline]
        return []


admin.site.register(TeacherProfile)
admin.site.register(StudentProfile)
