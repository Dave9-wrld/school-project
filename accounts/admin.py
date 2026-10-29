from django.contrib import admin
from .models import User, TeacherProfile, StudentProfile
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# Register your models here.

class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
    ('Role Information', {'fields': ('role', 'phone_number')}),
    ) 
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')

admin.site.register(TeacherProfile)
admin.site.register(StudentProfile)
