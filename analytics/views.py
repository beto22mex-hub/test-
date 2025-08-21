from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.views.decorators.http import require_http_methods
import json
from django.utils import timezone
from django.contrib.auth import authenticate
from datetime import datetime, timedelta

from serials.models import SerialNumber, AuthorizedPart
from operations.models import Operation, ProcessRecord
from defects.models import Defect
from .models import ProductionAlert
from operators.models import UserProfile
from .utils import get_shift_from_datetime, get_shift_display, get_current_shift


@login_required
def dashboard(request):
    """Main dashboard view with FPY, cycle time, and defects metrics by shift"""
    # Get recent serial numbers
    recent_serials = SerialNumber.objects.select_related(
        'authorized_part', 'created_by'
    ).order_by('-created_at')[:10]
    
    # Basic statistics
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    scrapped_serials = SerialNumber.objects.filter(status='SCRAPPED').count()
    
    # FPY: Percentage of serial numbers that pass all operations without defects
    serials_with_defects = Defect.objects.values('serial_number').distinct().count()
    fpy = round(((total_serials - serials_with_defects) / total_serials * 100) if total_serials > 0 else 0, 1)
    
    # Average time from creation to completion
    completed_serials_with_time = SerialNumber.objects.filter(
        status='COMPLETED',
        updated_at__isnull=False
    ).annotate(
        cycle_time=F('updated_at') - F('created_at')
    )
    
    avg_cycle_time_seconds = completed_serials_with_time.aggregate(
        avg_time=Avg('cycle_time')
    )['avg_time']
    
    avg_cycle_time_hours = 0
    if avg_cycle_time_seconds:
        avg_cycle_time_hours = round(avg_cycle_time_seconds.total_seconds() / 3600, 1)
    
    today = timezone.now().date()
    current_shift = get_current_shift()
    
    # Get defects by shift for today
    today_defects = Defect.objects.filter(created_at__date=today)
    
    shift_1_defects = 0
    shift_2_defects = 0
    
    for defect in today_defects:
        shift = get_shift_from_datetime(defect.created_at)
        if shift == 1:
            shift_1_defects += 1
        elif shift == 2:
            shift_2_defects += 1
    
    total_defects = Defect.objects.count()
    open_defects = Defect.objects.filter(status='OPEN').count()
    in_repair_defects = Defect.objects.filter(status='IN_REPAIR').count()
    resolved_defects = Defect.objects.filter(status='REPAIRED').count()
    
    # Defects by operation
    defects_by_operation = Defect.objects.values(
        'operation__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get active alerts
    active_alerts = ProductionAlert.objects.filter(
        is_active=True, 
        is_resolved=False
    ).order_by('-priority', '-created_at')[:5]
    
    context = {
        'recent_serials': recent_serials,
        'total_serials': total_serials,
        'completed_serials': completed_serials,
        'in_process_serials': in_process_serials,
        'pending_serials': pending_serials,
        'scrapped_serials': scrapped_serials,
        'completion_rate': round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1),
        'fpy': fpy,
        'avg_cycle_time_hours': avg_cycle_time_hours,
        'total_defects': total_defects,
        'open_defects': open_defects,
        'in_repair_defects': in_repair_defects,
        'resolved_defects': resolved_defects,
        'defects_by_operation': defects_by_operation,
        'active_alerts': active_alerts,
        'current_shift': current_shift,
        'current_shift_display': get_shift_display(current_shift),
        'shift_1_defects': shift_1_defects,
        'shift_2_defects': shift_2_defects,
        'shift_1_display': get_shift_display(1),
        'shift_2_display': get_shift_display(2),
    }
    
    return render(request, 'manufacturing/dashboard.html', context)


@login_required
def statistics_view(request):
    """Statistics and charts view"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_view_statistics)):
        messages.error(request, 'No tienes permisos para ver las estadísticas')
        return redirect('analytics:dashboard')
    
    # Basic statistics
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    scrapped_serials = SerialNumber.objects.filter(status='SCRAPPED').count()
    completion_rate = round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1)
    
    # FPY: Percentage of serial numbers that pass all operations without defects
    serials_with_defects = Defect.objects.values('serial_number').distinct().count()
    fpy = round(((total_serials - serials_with_defects) / total_serials * 100) if total_serials > 0 else 0, 1)
    
    # Operations statistics
    operations = Operation.objects.all().order_by('sequence_number')
    operations_labels = [op.name for op in operations]
    operations_completed = []
    operations_pending = []
    
    for operation in operations:
        completed_count = ProcessRecord.objects.filter(
            operation=operation, 
            status='COMPLETED'
        ).count()
        pending_count = ProcessRecord.objects.filter(
            operation=operation, 
            status__in=['PENDING', 'IN_PROCESS']
        ).count()
        
        operations_completed.append(completed_count)
        operations_pending.append(pending_count)
    
    # Production by day (last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    daily_production = SerialNumber.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Fill missing dates with 0
    production_dates = []
    production_counts = []
    current_date = start_date
    production_dict = {item['date']: item['count'] for item in daily_production}
    
    while current_date <= end_date:
        production_dates.append(current_date.strftime('%d/%m'))
        production_counts.append(production_dict.get(current_date, 0))
        current_date += timedelta(days=1)
    
    # Active alerts
    alerts = ProductionAlert.objects.filter(
        is_active=True, 
        is_resolved=False
    ).order_by('-priority', '-created_at')[:10]
    
    total_defects = Defect.objects.count()
    open_defects = Defect.objects.filter(status='OPEN').count()
    in_repair_defects = Defect.objects.filter(status='IN_REPAIR').count()
    resolved_defects = Defect.objects.filter(status='REPAIRED').count()
    
    # Defects by operation
    defects_by_operation = Defect.objects.values(
        'operation__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'total_serials': total_serials,
        'completed_serials': completed_serials,
        'in_process_serials': in_process_serials,
        'pending_serials': pending_serials,
        'scrapped_serials': scrapped_serials,
        'completion_rate': completion_rate,
        'operations_labels': json.dumps(operations_labels),
        'operations_completed': json.dumps(operations_completed),
        'operations_pending': json.dumps(operations_pending),
        'production_dates': json.dumps(production_dates),
        'production_counts': json.dumps(production_counts),
        'alerts': alerts,
        'fpy': fpy,
        'total_defects': total_defects,
        'open_defects': open_defects,
        'in_repair_defects': in_repair_defects,
        'resolved_defects': resolved_defects,
        'defects_by_operation': defects_by_operation,
    }
    
    return render(request, 'manufacturing/statistics.html', context)


@login_required
@require_http_methods(["GET"])
def api_statistics(request):
    """API endpoint for statistics data with enhanced metrics"""
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    scrapped_serials = SerialNumber.objects.filter(status='SCRAPPED').count()
    completion_rate = round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1)
    
    serials_with_defects = Defect.objects.values('serial_number').distinct().count()
    fpy = round(((total_serials - serials_with_defects) / total_serials * 100) if total_serials > 0 else 0, 1)
    
    total_defects = Defect.objects.count()
    open_defects = Defect.objects.filter(status='OPEN').count()
    in_repair_defects = Defect.objects.filter(status='IN_REPAIR').count()
    resolved_defects = Defect.objects.filter(status='REPAIRED').count()
    
    today = timezone.now().date()
    current_shift = get_current_shift()
    
    today_defects = Defect.objects.filter(created_at__date=today)
    shift_1_defects = 0
    shift_2_defects = 0
    
    for defect in today_defects:
        shift = get_shift_from_datetime(defect.created_at)
        if shift == 1:
            shift_1_defects += 1
        elif shift == 2:
            shift_2_defects += 1
    
    return JsonResponse({
        'total_serials': total_serials,
        'completed_serials': completed_serials,
        'in_process_serials': in_process_serials,
        'pending_serials': pending_serials,
        'scrapped_serials': scrapped_serials,
        'completion_rate': completion_rate,
        'fpy': fpy,
        'total_defects': total_defects,
        'open_defects': open_defects,
        'in_repair_defects': in_repair_defects,
        'resolved_defects': resolved_defects,
        'current_shift': current_shift,
        'shift_1_defects': shift_1_defects,
        'shift_2_defects': shift_2_defects,
    })


@login_required
@require_http_methods(["GET"])
def api_dashboard_data(request):
    """API endpoint for dashboard real-time data"""
    # Recent serial numbers
    recent_serials = SerialNumber.objects.select_related(
        'authorized_part', 'created_by'
    ).order_by('-created_at')[:10]
    
    # Active alerts
    active_alerts = ProductionAlert.objects.filter(
        is_active=True, 
        is_resolved=False
    ).order_by('-priority', '-created_at')[:5]
    
    serials_data = []
    for serial in recent_serials:
        serials_data.append({
            'serial_number': serial.serial_number,
            'order_number': serial.order_number,
            'part_number': serial.authorized_part.part_number,
            'status': serial.get_status_display(),
            'created_at': serial.created_at.strftime('%d/%m/%Y %H:%M'),
            'progress': serial.get_completion_percentage(),
        })
    
    alerts_data = []
    for alert in active_alerts:
        alerts_data.append({
            'type': alert.get_alert_type_display(),
            'message': alert.message,
            'priority': alert.get_priority_display(),
            'created_at': alert.created_at.strftime('%d/%m/%Y %H:%M'),
        })
    
    return JsonResponse({
        'recent_serials': serials_data,
        'active_alerts': alerts_data,
    })


@login_required
@require_http_methods(["POST"])
def assign_operator(request):
    """Assign current user to a free operation"""
    try:
        data = json.loads(request.body)
        operation_id = data.get('operation_id')
        
        from operations.models import Operation, ProcessRecord
        from django.db import transaction
        
        with transaction.atomic():
            operation = get_object_or_404(Operation, id=operation_id)
            
            # Check if user already has an operation in progress
            existing_assignment = ProcessRecord.objects.filter(
                assigned_operator=request.user,
                status='IN_PROGRESS'
            ).first()
            
            if existing_assignment:
                return JsonResponse({
                    'success': False,
                    'error': f'Ya tienes una operación en progreso: {existing_assignment.operation.name}. Debes completarla o liberarla primero.'
                })
            
            # Find a free operation (pending without assigned operator)
            free_operation = ProcessRecord.objects.filter(
                operation=operation,
                status='PENDING',
                assigned_operator__isnull=True
            ).first()
            
            if not free_operation:
                return JsonResponse({
                    'success': False,
                    'error': 'No hay operaciones libres disponibles para esta operación.'
                })
            
            # Assign the operation
            free_operation.assigned_operator = request.user
            free_operation.status = 'IN_PROGRESS'
            free_operation.started_at = timezone.now()
            free_operation.assigned_at = timezone.now()
            free_operation.save()
            
            # Update serial number status if needed
            if free_operation.serial_number.status == 'CREATED':
                free_operation.serial_number.status = 'IN_PROCESS'
                free_operation.serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Te has asignado exitosamente a la operación {operation.name}.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al asignar operación: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def change_operator(request):
    """Change operator assignment (admin/supervisor only)"""
    try:
        # Check permissions
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'userprofile') and 
                 request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
            return JsonResponse({
                'success': False,
                'error': 'No tienes permisos para cambiar asignaciones de operadores.'
            })
        
        data = json.loads(request.body)
        operation_id = data.get('operation_id')
        new_operator_id = data.get('new_operator_id')
        
        from operations.models import Operation, ProcessRecord
        from django.contrib.auth.models import User
        from django.db import transaction
        
        with transaction.atomic():
            operation = get_object_or_404(Operation, id=operation_id)
            new_operator = get_object_or_404(User, id=new_operator_id)
            
            # Validate new operator
            if not hasattr(new_operator, 'userprofile') or new_operator.userprofile.role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
                return JsonResponse({
                    'success': False,
                    'error': 'El usuario seleccionado no es un operador válido.'
                })
            
            # Check if new operator already has an operation in progress
            existing_assignment = ProcessRecord.objects.filter(
                assigned_operator=new_operator,
                status='IN_PROGRESS'
            ).first()
            
            if existing_assignment:
                operator_name = new_operator.get_full_name() or new_operator.username
                return JsonResponse({
                    'success': False,
                    'error': f'{operator_name} ya tiene una operación en progreso: {existing_assignment.operation.name}.'
                })
            
            # Find current assignment for this operation
            current_assignment = ProcessRecord.objects.filter(
                operation=operation,
                status='IN_PROGRESS',
                assigned_operator__isnull=False
            ).first()
            
            if not current_assignment:
                return JsonResponse({
                    'success': False,
                    'error': 'No se encontró una asignación activa para esta operación.'
                })
            
            # Change the operator
            current_assignment.assigned_operator = new_operator
            current_assignment.assigned_at = timezone.now()
            current_assignment.save()
            
            operator_name = new_operator.get_full_name() or new_operator.username
            return JsonResponse({
                'success': True,
                'message': f'Operación {operation.name} reasignada exitosamente a {operator_name}.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al cambiar operador: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def start_process(request):
    """Start a process that is assigned to the current user"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        
        from django.db import transaction
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            # Verify the process is assigned to current user
            if process_record.assigned_operator != request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'No tienes permisos para iniciar este proceso.'
                })
            
            # Verify the process is in correct status
            if process_record.status != 'PENDING':
                return JsonResponse({
                    'success': False,
                    'message': 'Este proceso no está en estado pendiente.'
                })
            
            # Start the process
            process_record.status = 'IN_PROGRESS'
            process_record.started_at = timezone.now()
            process_record.save()
            
            # Update serial number status if needed
            if process_record.serial_number.status == 'CREATED':
                process_record.serial_number.status = 'IN_PROCESS'
                process_record.serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Proceso {process_record.operation.name} iniciado exitosamente.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al iniciar proceso: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def complete_process(request):
    """Complete a process with password validation"""
    try:
        process_record_id = request.POST.get('process_record_id')
        password = request.POST.get('password')
        notes = request.POST.get('notes', '')
        
        # Validate password
        if not password:
            return JsonResponse({
                'success': False,
                'message': 'Debes ingresar tu contraseña para completar el proceso.'
            })
        
        # Authenticate user with provided password
        user = authenticate(username=request.user.username, password=password)
        if not user:
            return JsonResponse({
                'success': False,
                'message': 'Contraseña incorrecta. No se puede completar el proceso.'
            })
        
        from django.db import transaction
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            # Verify the process is assigned to current user
            if process_record.assigned_operator != request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'No tienes permisos para completar este proceso.'
                })
            
            # Verify the process is in progress
            if process_record.status != 'IN_PROGRESS':
                return JsonResponse({
                    'success': False,
                    'message': 'Este proceso no está en progreso.'
                })
            
            # Complete the process
            process_record.status = 'APPROVED'
            process_record.processed_at = timezone.now()
            process_record.processed_by = request.user
            process_record.notes = notes
            process_record.save()
            
            # Check if this was the last operation for the serial number
            serial_number = process_record.serial_number
            remaining_operations = ProcessRecord.objects.filter(
                serial_number=serial_number,
                status__in=['PENDING', 'IN_PROGRESS']
            ).count()
            
            if remaining_operations == 0:
                # All operations completed, mark serial as completed
                serial_number.status = 'COMPLETED'
                serial_number.save()
            else:
                # Move to next operation
                next_operation = ProcessRecord.objects.filter(
                    serial_number=serial_number,
                    status='PENDING',
                    operation__sequence_number__gt=process_record.operation.sequence_number
                ).order_by('operation__sequence_number').first()
                
                if next_operation:
                    # Serial continues to next operation
                    serial_number.status = 'IN_PROCESS'
                    serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Proceso {process_record.operation.name} completado exitosamente.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al completar proceso: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def reject_process(request):
    """Reject a process with password validation and send to repair"""
    try:
        process_record_id = request.POST.get('process_record_id')
        password = request.POST.get('password')
        reject_reason = request.POST.get('reject_reason', '')
        
        # Validate password
        if not password:
            return JsonResponse({
                'success': False,
                'message': 'Debes ingresar tu contraseña para rechazar el proceso.'
            })
        
        # Validate reject reason
        if not reject_reason.strip():
            return JsonResponse({
                'success': False,
                'message': 'Debes especificar el motivo del rechazo.'
            })
        
        # Authenticate user with provided password
        user = authenticate(username=request.user.username, password=password)
        if not user:
            return JsonResponse({
                'success': False,
                'message': 'Contraseña incorrecta. No se puede rechazar el proceso.'
            })
        
        from django.db import transaction
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            # Verify the process is assigned to current user
            if process_record.assigned_operator != request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'No tienes permisos para rechazar este proceso.'
                })
            
            # Verify the process is in progress
            if process_record.status != 'IN_PROGRESS':
                return JsonResponse({
                    'success': False,
                    'message': 'Este proceso no está en progreso.'
                })
            
            # Reject the process
            process_record.status = 'REJECTED'
            process_record.processed_at = timezone.now()
            process_record.processed_by = request.user
            process_record.notes = f'RECHAZADO: {reject_reason}'
            process_record.save()
            
            # Create defect record
            defect = Defect.objects.create(
                serial_number=process_record.serial_number,
                operation=process_record.operation,
                defect_type='PROCESS_FAILURE',
                description=f'Proceso rechazado: {reject_reason}',
                severity='MEDIUM',
                status='OPEN',
                detected_by=request.user,
                detected_at=timezone.now()
            )
            
            # Mark serial number as failed and needing repair
            serial_number = process_record.serial_number
            serial_number.status = 'FAILED'
            serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Proceso {process_record.operation.name} rechazado. El número de serie ha sido enviado a reparación.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al rechazar proceso: {str(e)}'
        })
