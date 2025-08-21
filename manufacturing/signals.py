from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from operators.models import UserProfile
from serials.models import SerialNumber
from operations.models import ProcessRecord, Operation


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(
            user=instance,
            employee_id=f"EMP{instance.id:04d}",
            role='OPERATOR'
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()


@receiver(post_save, sender=SerialNumber)
def create_process_records(sender, instance, created, **kwargs):
    """Create ProcessRecord entries for all active operations when SerialNumber is created"""
    if created:
        operations = Operation.objects.filter(is_active=True).order_by('sequence_number')
        for operation in operations:
            ProcessRecord.objects.create(
                serial_number=instance,
                operation=operation,
                status='PENDING'
            )


@receiver(pre_save, sender=ProcessRecord)
def update_process_timestamps(sender, instance, **kwargs):
    """Update timestamps based on status changes"""
    if instance.pk:  # Only for existing records
        try:
            old_instance = ProcessRecord.objects.get(pk=instance.pk)
            
            # If status changed to IN_PROGRESS, set started_at
            if (old_instance.status != 'IN_PROGRESS' and 
                instance.status == 'IN_PROGRESS' and 
                not instance.started_at):
                instance.started_at = timezone.now()
            
            # If status changed to APPROVED, set completed_at
            if (old_instance.status != 'APPROVED' and 
                instance.status == 'APPROVED' and 
                not instance.completed_at):
                instance.completed_at = timezone.now()
                
        except ProcessRecord.DoesNotExist:
            pass


@receiver(post_save, sender=ProcessRecord)
def update_serial_status(sender, instance, **kwargs):
    """Update SerialNumber status based on ProcessRecord changes"""
    serial = instance.serial_number
    
    # Check if all operations are approved
    total_operations = Operation.objects.filter(is_active=True).count()
    approved_operations = serial.process_records.filter(status='APPROVED').count()
    
    if approved_operations == total_operations:
        serial.status = 'COMPLETED'
        serial.completed_at = timezone.now()
    elif approved_operations > 0:
        serial.status = 'IN_PROCESS'
    else:
        serial.status = 'CREATED'
    
    serial.save()
