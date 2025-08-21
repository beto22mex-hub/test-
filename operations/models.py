from django.db import models
from django.contrib.auth.models import User


class Operation(models.Model):
    """Model for manufacturing operations"""
    name = models.CharField(
        max_length=100,
        help_text="Nombre de la operación"
    )
    description = models.TextField(
        help_text="Descripción detallada de la operación"
    )
    sequence_number = models.PositiveIntegerField(
        unique=True,
        help_text="Orden de secuencia (1-7)"
    )
    estimated_time_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Tiempo estimado en minutos"
    )
    requires_approval = models.BooleanField(
        default=True,
        help_text="Requiere aprobación de usuario"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Operación activa"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Operación"
        verbose_name_plural = "Operaciones"
        ordering = ['sequence_number']

    def __str__(self):
        return f"{self.sequence_number}. {self.name}"


class ProcessRecord(models.Model):
    """Model to track manufacturing process for each serial number"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('IN_PROGRESS', 'En Progreso'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
    ]
    
    serial_number = models.ForeignKey(
        'serials.SerialNumber',
        on_delete=models.CASCADE,
        related_name='process_records'
    )
    
    operation = models.ForeignKey(
        Operation,
        on_delete=models.PROTECT
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # User who performed/approved the operation
    processed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='processed_operations'
    )
    
    # Operador asignado actualmente a esta operación
    assigned_operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_operations',
        help_text="Operador actualmente asignado a esta operación"
    )
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Additional information
    notes = models.TextField(
        blank=True,
        help_text="Notas adicionales sobre el proceso"
    )
    
    # Quality control
    quality_check_passed = models.BooleanField(
        default=False,
        help_text="Control de calidad aprobado"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        help_text="Razón del rechazo (se crea defecto automáticamente)"
    )
    
    defect_type = models.CharField(
        max_length=20,
        blank=True,
        help_text="Tipo de defecto cuando se rechaza"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registro de Proceso"
        verbose_name_plural = "Registros de Proceso"
        unique_together = ['serial_number', 'operation']
        ordering = ['serial_number', 'operation__sequence_number']

    def __str__(self):
        return f"{self.serial_number} - {self.operation.name} ({self.status})"
    
    def is_assigned(self):
        """Verifica si la operación está asignada a un operador"""
        return self.assigned_operator is not None and self.status == 'IN_PROGRESS'
    
    def can_be_assigned_to(self, user):
        """Verifica si la operación puede ser asignada al usuario"""
        # Solo operadores pueden ser asignados
        if not hasattr(user, 'userprofile') or user.userprofile.role != 'OPERATOR':
            return False
        
        # La operación debe estar pendiente
        if self.status != 'PENDING':
            return False
            
        # El operador no debe tener otra operación asignada
        active_assignment = ProcessRecord.objects.filter(
            assigned_operator=user,
            status='IN_PROGRESS'
        ).exists()
        
        return not active_assignment
