from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile for manufacturing system"""
    
    ROLE_CHOICES = [
        ('OPERATOR', 'Operador'),
        ('SUPERVISOR', 'Supervisor'),
        ('QUALITY', 'Control de Calidad'),
        ('ADMIN', 'Administrador'),
        ('REPAIRER', 'Reparador'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active_operator = models.BooleanField(default=True)
    
    # Permissions
    can_approve_operations = models.BooleanField(default=False)
    can_generate_serials = models.BooleanField(default=True)
    can_view_statistics = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"
