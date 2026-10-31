from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from .models import User, TeacherProfile, StudentProfile


@receiver(pre_save, sender=User)
def detect_password_change(sender, instance, using, raw=False, **kwargs):
    instance._password_changed = False
    if not raw and instance.pk:
        previous = sender.objects.using(using).filter(pk=instance.pk).values_list('password', flat=True).first()
        instance._password_changed = previous is not None and previous != instance.password


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, using, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    if instance.role == User.Role.TEACHER:
        TeacherProfile.objects.using(using).get_or_create(user=instance)
    elif instance.role == User.Role.STUDENT:
        StudentProfile.objects.using(using).get_or_create(user=instance)
    elif instance.role == User.Role.ADMIN:
        if not instance.is_staff:
            sender.objects.using(using).filter(pk=instance.pk).update(is_staff=True)

    if getattr(instance, '_password_changed', False) and (update_fields is None or 'password' in update_fields):
        Token.objects.using(using).filter(user=instance).delete()


@receiver(user_logged_out)
def revoke_token_on_logout(sender, user, **kwargs):
    if user is not None:
        Token.objects.filter(user=user).delete()
