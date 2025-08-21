from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from operators.models import UserProfile
from serials.models import AuthorizedPart, SerialNumber
from operations.models import Operation, ProcessRecord
from analytics.models import ProductionAlert


# Inline admin for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil'


# Extend User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(AuthorizedPart)
class AuthorizedPartAdmin(admin.ModelAdmin):
    list_display = ['part_number', 'description', 'revision', 'is_active', 'created_at']
    list_filter = ['is_active', 'revision', 'created_at']
    search_fields = ['part_number', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = [
        'serial_number', 'order_number', 'authorized_part', 
        'status', 'completion_percentage', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'authorized_part', 'created_at', 'created_by']
    search_fields = ['serial_number', 'order_number', 'authorized_part__part_number']
    readonly_fields = ['created_at', 'updated_at', 'completion_percentage']
    
    def completion_percentage(self, obj):
        return f"{obj.completion_percentage}%"
    completion_percentage.short_description = "Completado"


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = [
        'sequence_number', 'name', 'estimated_time_minutes', 
        'requires_approval', 'is_active'
    ]
    list_filter = ['requires_approval', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['sequence_number']


@admin.register(ProcessRecord)
class ProcessRecordAdmin(admin.ModelAdmin):
    list_display = [
        'serial_number', 'operation', 'status', 'processed_by', 
        'quality_check_passed', 'completed_at'
    ]
    list_filter = [
        'status', 'operation', 'quality_check_passed', 
        'completed_at', 'processed_by'
    ]
    search_fields = ['serial_number__serial_number', 'operation__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProductionAlert)
class ProductionAlertAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'alert_type', 'priority', 'is_resolved', 
        'created_by', 'created_at'
    ]
    list_filter = [
        'alert_type', 'priority', 'is_resolved', 'created_at'
    ]
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'resolved_at']


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
