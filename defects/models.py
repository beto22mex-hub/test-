from django.db import models
from django.contrib.auth.models import User


class Defect(models.Model):
    """Model to track defects found during manufacturing"""
    
    DEFECT_STATUS_CHOICES = [
        ('OPEN', 'Abierto'),
        ('IN_REPAIR', 'En Reparación'),
        ('REPAIRED', 'Reparado'),
        ('SCRAPPED', 'Desechado'),
    ]
    
    DEFECT_TYPE_CHOICES = [
        ('DIMENSIONAL', 'Dimensional'),
        ('VISUAL', 'Visual'),
        ('FUNCTIONAL', 'Funcional'),
        ('MATERIAL', 'Material'),
        ('ASSEMBLY', 'Ensamble'),
        ('OTHER', 'Otro'),
    ]
    
    serial_number = models.ForeignKey(
        'serials.SerialNumber',
        on_delete=models.CASCADE,
        related_name='defects'
    )
    
    operation = models.ForeignKey(
        'operations.Operation',
        on_delete=models.PROTECT,
        help_text="Operación donde se detectó el defecto"
    )
    
    defect_type = models.CharField(
        max_length=20,
        choices=DEFECT_TYPE_CHOICES,
        default='OTHER'
    )
    
    description = models.TextField(
        help_text="Descripción detallada del defecto"
    )
    
    status = models.CharField(
        max_length=20,
        choices=DEFECT_STATUS_CHOICES,
        default='OPEN'
    )
    
    # Users involved
    reported_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='reported_defects',
        help_text="Usuario que reportó el defecto"
    )
    
    assigned_repairer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_defects',
        help_text="Reparador asignado"
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_defects',
        help_text="Usuario que resolvió el defecto"
    )
    
    # Repair information
    repair_notes = models.TextField(
        blank=True,
        help_text="Notas sobre la reparación realizada"
    )
    
    return_to_operation = models.ForeignKey(
        'operations.Operation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='returned_serials',
        help_text="Operación a la que regresa después de reparación"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Defecto"
        verbose_name_plural = "Defectos"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.serial_number} - {self.defect_type} ({self.status})"
