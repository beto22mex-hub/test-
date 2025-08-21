from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from .models import Defect, SerialNumber, Operation, ProcessRecord
from .decorators import supervisor_or_admin_required
from django.views.decorators.http import require_http_methods
import json


@login_required
@supervisor_or_admin_required
def defects_dashboard(request):
    """Dashboard principal de defectos para supervisores y administradores"""
    
    # Estadísticas generales
    total_defects = Defect.objects.count()
    open_defects = Defect.objects.filter(status='OPEN').count()
    in_repair_defects = Defect.objects.filter(status='IN_REPAIR').count()
    resolved_defects = Defect.objects.filter(status__in=['REPAIRED', 'SCRAPPED']).count()
    
    # Defectos por tipo
    defects_by_type = Defect.objects.values('defect_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Defectos recientes
    recent_defects = Defect.objects.select_related(
        'serial_number', 'operation', 'reported_by'
    ).order_by('-created_at')[:10]
    
    # Números de serie con defectos activos
    defective_serials = SerialNumber.objects.filter(
        defects__status__in=['OPEN', 'IN_REPAIR']
    ).distinct().select_related('authorized_part')
    
    context = {
        'total_defects': total_defects,
        'open_defects': open_defects,
        'in_repair_defects': in_repair_defects,
        'resolved_defects': resolved_defects,
        'defects_by_type': defects_by_type,
        'recent_defects': recent_defects,
        'defective_serials': defective_serials,
    }
    
    return render(request, 'manufacturing/defects_dashboard.html', context)


@login_required
def repairer_dashboard(request):
    """Dashboard específico para reparadores"""
    
    # Verificar que el usuario sea reparador
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role != 'REPAIRER':
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('manufacturing:dashboard')
    
    # Defectos asignados al reparador
    assigned_defects = Defect.objects.filter(
        assigned_repairer=request.user,
        status__in=['OPEN', 'IN_REPAIR']
    ).select_related('serial_number', 'operation')
    
    # Defectos disponibles para asignar
    available_defects = Defect.objects.filter(
        assigned_repairer__isnull=True,
        status='OPEN'
    ).select_related('serial_number', 'operation')
    
    # Historial de reparaciones
    repair_history = Defect.objects.filter(
        resolved_by=request.user
    ).select_related('serial_number', 'operation').order_by('-resolved_at')[:10]
    
    context = {
        'assigned_defects': assigned_defects,
        'available_defects': available_defects,
        'repair_history': repair_history,
    }
    
    return render(request, 'manufacturing/repairer_dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def assign_defect(request):
    """Asignar defecto a reparador"""
    
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role != 'REPAIRER':
        return JsonResponse({'success': False, 'error': 'Sin permisos'})
    
    try:
        data = json.loads(request.body)
        defect_id = data.get('defect_id')
        
        defect = get_object_or_404(Defect, id=defect_id, status='OPEN')
        
        # Verificar que no esté asignado
        if defect.assigned_repairer:
            return JsonResponse({'success': False, 'error': 'Defecto ya asignado'})
        
        # Asignar al reparador
        defect.assigned_repairer = request.user
        defect.status = 'IN_REPAIR'
        defect.assigned_at = timezone.now()
        defect.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def resolve_defect(request):
    """Resolver defecto (reparar o desechar)"""
    
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role != 'REPAIRER':
        return JsonResponse({'success': False, 'error': 'Sin permisos'})
    
    try:
        data = json.loads(request.body)
        defect_id = data.get('defect_id')
        resolution = data.get('resolution')  # 'REPAIRED' or 'SCRAPPED'
        repair_notes = data.get('repair_notes', '')
        return_to_operation_id = data.get('return_to_operation_id')
        
        defect = get_object_or_404(Defect, id=defect_id, assigned_repairer=request.user)
        
        # Actualizar defecto
        defect.status = resolution
        defect.repair_notes = repair_notes
        defect.resolved_by = request.user
        defect.resolved_at = timezone.now()
        
        if resolution == 'REPAIRED' and return_to_operation_id:
            operation = get_object_or_404(Operation, id=return_to_operation_id)
            defect.return_to_operation = operation
            
            # Actualizar estado del número de serie
            serial = defect.serial_number
            serial.status = 'IN_PROCESS'
            serial.save()
            
            # Crear o actualizar ProcessRecord para la operación de retorno
            process_record, created = ProcessRecord.objects.get_or_create(
                serial_number=serial,
                operation=operation,
                defaults={
                    'status': 'PENDING',
                    'notes': f'Regresado después de reparación de defecto: {defect.description}'
                }
            )
            
            if not created:
                process_record.status = 'PENDING'
                process_record.notes += f'\nRegresado después de reparación: {defect.description}'
                process_record.save()
                
        elif resolution == 'SCRAPPED':
            # Marcar número de serie como desechado
            serial = defect.serial_number
            serial.status = 'SCRAPPED'
            serial.save()
        
        defect.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def defect_detail(request, defect_id):
    """Vista detallada de un defecto"""
    
    defect = get_object_or_404(Defect, id=defect_id)
    
    # Verificar permisos
    user_role = getattr(request.user.userprofile, 'role', None) if hasattr(request.user, 'userprofile') else None
    
    if user_role not in ['SUPERVISOR', 'ADMIN', 'REPAIRER']:
        messages.error(request, 'No tienes permisos para ver este defecto.')
        return redirect('manufacturing:dashboard')
    
    # Si es reparador, solo puede ver sus defectos asignados
    if user_role == 'REPAIRER' and defect.assigned_repairer != request.user:
        messages.error(request, 'No tienes permisos para ver este defecto.')
        return redirect('manufacturing:repairer_dashboard')
    
    # Obtener operaciones disponibles para retorno
    operations = Operation.objects.filter(is_active=True).order_by('sequence_number')
    
    context = {
        'defect': defect,
        'operations': operations,
        'user_role': user_role,
    }
    
    return render(request, 'manufacturing/defect_detail.html', context)
