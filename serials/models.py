from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class AuthorizedPart(models.Model):
    """Model for authorized parts that can be used in serial numbers"""
    part_number = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Número de parte autorizado"
    )
    sku = models.CharField(
        max_length=50,
        help_text="SKU del componente para exportación CSV"
    )
    description = models.TextField(help_text="Descripción del componente")
    revision = models.CharField(
        max_length=10, 
        default="A",
        help_text="Revisión actual del componente"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indica si el componente está activo para uso"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Componente Autorizado"
        verbose_name_plural = "Componentes Autorizados"
        ordering = ['part_number']

    def __str__(self):
        return f"{self.part_number} - {self.description}"


class SerialNumber(models.Model):
    """Model for serial numbers with [YEAR][MONTH]###-###M format"""
    
    serial_validator = RegexValidator(
        regex=r'^[K-Z][A-L]\d{3}-\d{3}M$',
        message='El número de serie debe tener el formato [AÑO][MES]###-###M (ej: KA001-001M)'
    )
    
    serial_number = models.CharField(
        max_length=12,  # Increased length for new format
        unique=True,
        validators=[serial_validator],
        help_text="Formato: [AÑO][MES]###-###M (ej: KA001-001M para enero 2025)"
    )
    
    order_number = models.CharField(
        max_length=50,
        help_text="Número de orden asociado"
    )
    
    # Part information
    authorized_part = models.ForeignKey(
        AuthorizedPart,
        on_delete=models.PROTECT,
        help_text="Componente autorizado asociado"
    )
    
    # Status tracking
    STATUS_CHOICES = [
        ('CREATED', 'Creado'),
        ('IN_PROCESS', 'En Proceso'),
        ('COMPLETED', 'Completado'),
        ('REJECTED', 'Rechazado'),
        ('DEFECTIVE', 'Con Defecto'),
        ('SCRAPPED', 'Desechado'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='CREATED'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # User who created the serial number
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_serials'
    )

    class Meta:
        verbose_name = "Número de Serie"
        verbose_name_plural = "Números de Serie"
        ordering = ['-created_at']

    def __str__(self):
        return self.serial_number

    @property
    def completion_percentage(self):
        """Calculate completion percentage based on approved operations"""
        from operations.models import Operation
        total_operations = Operation.objects.filter(is_active=True).count()
        if total_operations == 0:
            return 0
        
        completed_operations = self.process_records.filter(
            status='APPROVED'
        ).count()
        
        return round((completed_operations / total_operations) * 100, 2)

    @property
    def current_operation(self):
        """Get the next operation to be performed"""
        from operations.models import Operation
        completed_ops = self.process_records.filter(
            status='APPROVED'
        ).values_list('operation__sequence_number', flat=True)
        
        next_operation = Operation.objects.filter(
            is_active=True
        ).exclude(
            sequence_number__in=completed_ops
        ).order_by('sequence_number').first()
        
        return next_operation

    @property
    def has_open_defects(self):
        """Check if serial number has open defects"""
        return self.defects.filter(status__in=['OPEN', 'IN_REPAIR']).exists()
    
    @property
    def defect_history(self):
        """Get all defects for this serial number"""
        return self.defects.all().order_by('-created_at')
    
    @property
    def first_pass_yield(self):
        """Calculate if this serial passed first time (no defects)"""
        return not self.defects.exists()
