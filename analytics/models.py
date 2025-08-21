from django.db import models
from django.contrib.auth.models import User


class ProductionAlert(models.Model):
    """Model for production alerts and notifications"""
    
    ALERT_TYPES = [
        ('DELAY', 'Retraso en Producción'),
        ('QUALITY', 'Problema de Calidad'),
        ('MAINTENANCE', 'Mantenimiento Requerido'),
        ('INVENTORY', 'Problema de Inventario'),
        ('GENERAL', 'Alerta General'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Baja'),
        ('MEDIUM', 'Media'),
        ('HIGH', 'Alta'),
        ('CRITICAL', 'Crítica'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    
    # Related objects
    serial_number = models.ForeignKey(
        'serials.SerialNumber',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_resolved = models.BooleanField(default=False)
    
    # Users
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_alerts'
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de Producción"
        verbose_name_plural = "Alertas de Producción"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.priority})"


class ProductionMetrics(models.Model):
    """Model to store daily production metrics"""
    
    date = models.DateField(unique=True)
    
    # Production counts
    total_serials_started = models.PositiveIntegerField(default=0)
    total_serials_completed = models.PositiveIntegerField(default=0)
    total_defects_found = models.PositiveIntegerField(default=0)
    total_scrapped = models.PositiveIntegerField(default=0)
    
    # FPY (First Pass Yield)
    first_pass_yield_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Porcentaje de números de serie que pasaron sin defectos"
    )
    
    # Cycle time
    average_cycle_time_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Tiempo promedio de ciclo en minutos"
    )
    
    # Defect rate
    defect_rate_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Porcentaje de defectos encontrados"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Métrica de Producción"
        verbose_name_plural = "Métricas de Producción"
        ordering = ['-date']
    
    def __str__(self):
        return f"Métricas {self.date} - FPY: {self.first_pass_yield_percentage}%"
