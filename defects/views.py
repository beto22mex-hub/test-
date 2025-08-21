from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from .models import Defect
from serials.models import SerialNumber
from operations.models import Operation, ProcessRecord
from operators.models import UserProfile
from operators.decorators import supervisor_or_admin_required
import json

@login_required
@supervisor_or_admin_required
def defects_dashboard(request):
    """Dashboard for managing defects - accessible by supervisors and admins"""
    defects = Defect.objects.select_related(
        'serial_number', 'operation', 'reported_by', 'assigned_repairer'  # corregido assigned_to a assigned_repairer
    ).order_by('-created_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        defects = defects.filter(status=status_filter)
    
    # Statistics
    stats = {
        'total_defects': defects.count(),
        'open_defects': defects.filter(status='OPEN').count(),
        'in_repair': defects.filter(status='IN_REPAIR').count(),
        'repaired': defects.filter(status='REPAIRED').count(),  # corregido RESOLVED a REPAIRED
        'scrapped': defects.filter(status='SCRAPPED').count(),
    }
    
    context = {
        'defects': defects[:50],  # Limit to 50 for performance
        'stats': stats,
        'status_choices': Defect.DEFECT_STATUS_CHOICES,  # corregido STATUS_CHOICES a DEFECT_STATUS_CHOICES
    }
    return render(request, 'defects/defects_dashboard.html', context)

@login_required
def repairer_dashboard(request):
    """Dashboard for repairers to manage their assigned defects"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only repairers can access this view
    if user_profile.role not in ['REPAIRER', 'ADMIN']:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('analytics:dashboard')
    
    # Get defects assigned to this repairer
    assigned_defects = Defect.objects.filter(
        assigned_repairer=request.user,  # corregido assigned_to a assigned_repairer
        status__in=['OPEN', 'IN_REPAIR']
    ).select_related('serial_number', 'operation').order_by('-created_at')
    
    # Get completed defects for history
    completed_defects = Defect.objects.filter(
        assigned_repairer=request.user,  # corregido assigned_to a assigned_repairer
        status__in=['REPAIRED', 'SCRAPPED']  # corregido RESOLVED a REPAIRED
    ).select_related('serial_number', 'operation').order_by('-created_at')[:20]  # corregido updated_at a created_at
    
    context = {
        'assigned_defects': assigned_defects,
        'completed_defects': completed_defects,
        'user_profile': user_profile,
    }
    return render(request, 'defects/repairer_dashboard.html', context)

@login_required
def defect_detail(request, defect_id):
    """Detail view for a specific defect"""
    defect = get_object_or_404(Defect.objects.select_related(
        'serial_number', 'operation', 'reported_by', 'assigned_repairer'  # corregido assigned_to a assigned_repairer
    ), id=defect_id)
    
    # Get defect history for this serial number
    defect_history = Defect.objects.filter(
        serial_number=defect.serial_number
    ).exclude(id=defect.id).order_by('-created_at')
    
    context = {
        'defect': defect,
        'defect_history': defect_history,
        'status_choices': Defect.DEFECT_STATUS_CHOICES,  # corregido STATUS_CHOICES a DEFECT_STATUS_CHOICES
    }
    return render(request, 'defects/defect_detail.html', context)

@login_required
@require_POST
@supervisor_or_admin_required
def assign_defect(request):
    """API endpoint to assign a defect to a repairer"""
    try:
        data = json.loads(request.body)
        defect_id = data.get('defect_id')
        repairer_id = data.get('repairer_id')
        
        defect = get_object_or_404(Defect, id=defect_id)
        repairer = get_object_or_404(UserProfile, id=repairer_id, role='REPAIRER')
        
        defect.assigned_repairer = repairer.user  # corregido assigned_to a assigned_repairer
        defect.status = 'IN_REPAIR'
        defect.assigned_at = timezone.now()  # agregado timestamp de asignación
        defect.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Defecto asignado a {repairer.user.get_full_name() or repairer.user.username}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al asignar defecto: {str(e)}'
        })

@login_required
@require_POST
def resolve_defect(request):
    """API endpoint to resolve a defect"""
    try:
        data = json.loads(request.body)
        defect_id = data.get('defect_id')
        repair_notes = data.get('repair_notes')  # corregido resolution a repair_notes
        return_to_operation = data.get('return_to_operation')
        
        defect = get_object_or_404(Defect, id=defect_id)
        user_profile = get_object_or_404(UserProfile, user=request.user)
        
        # Check permissions
        if user_profile.role not in ['REPAIRER', 'ADMIN'] and defect.assigned_repairer != request.user:  # corregido assigned_to a assigned_repairer
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para resolver este defecto'
            })
        
        # Update defect
        defect.repair_notes = repair_notes  # corregido resolution a repair_notes
        defect.resolved_at = timezone.now()
        defect.resolved_by = request.user  # agregado resolved_by
        
        if return_to_operation:
            defect.status = 'REPAIRED'  # corregido RESOLVED a REPAIRED
            # Return serial number to specified operation
            operation = get_object_or_404(Operation, id=return_to_operation)
            defect.return_to_operation = operation  # agregado return_to_operation
            
            # Create or update process record
            process_record, created = ProcessRecord.objects.get_or_create(
                serial_number=defect.serial_number,
                operation=operation,
                defaults={
                    'status': 'PENDING',
                    'assigned_operator': None
                }
            )
            if not created:
                process_record.status = 'PENDING'
                process_record.assigned_operator = None
                process_record.save()
                
        else:
            defect.status = 'SCRAPPED'
            # Mark serial number as scrapped
            defect.serial_number.status = 'SCRAPPED'
            defect.serial_number.save()
        
        defect.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Defecto resuelto exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al resolver defecto: {str(e)}'
        })
