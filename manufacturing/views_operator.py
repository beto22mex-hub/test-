from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from operations.models import ProcessRecord, Operation
from serials.models import SerialNumber
from defects.models import Defect
from .decorators import operator_required, supervisor_or_admin_required
import json


@login_required
@operator_required
def operator_dashboard(request):
    """Dashboard principal para operadores"""
    user = request.user
    user_role = user.userprofile.role
    
    # Operación actualmente asignada
    current_assignment = ProcessRecord.objects.filter(
        assigned_operator=user,
        status='IN_PROGRESS'
    ).select_related('serial_number', 'operation', 'serial_number__authorized_part').first()
    
    if user_role == 'OPERATOR':
        available_operations = ProcessRecord.objects.filter(
            status='PENDING',
            assigned_operator__isnull=True
        ).select_related('serial_number', 'operation', 'serial_number__authorized_part').order_by(
            'operation__sequence_number', 'created_at'
        )[:10]
    else:
        # Supervisores y admin ven todas las operaciones
        available_operations = ProcessRecord.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).select_related('serial_number', 'operation', 'serial_number__authorized_part', 'assigned_operator').order_by(
            'operation__sequence_number', 'created_at'
        )[:10]
    
    # Historial de operaciones completadas por el operador
    completed_operations = ProcessRecord.objects.filter(
        processed_by=user,
        status='APPROVED'
    ).select_related('serial_number', 'operation').order_by('-completed_at')[:5]
    
    # Estadísticas del operador
    total_completed = ProcessRecord.objects.filter(
        processed_by=user,
        status='APPROVED'
    ).count()
    
    context = {
        'current_assignment': current_assignment,
        'available_operations': available_operations,
        'completed_operations': completed_operations,
        'total_completed': total_completed,
        'user_role': user_role,
    }
    
    return render(request, 'manufacturing/operator_dashboard.html', context)


@login_required
@operator_required
def operation_work_view(request, process_record_id):
    """Vista de trabajo para una operación específica con selección de números de serie"""
    process_record = get_object_or_404(
        ProcessRecord, 
        id=process_record_id,
        assigned_operator=request.user,
        status='IN_PROGRESS'
    )
    
    # Obtener números de serie disponibles para esta operación
    # Solo números de serie que están en la operación correcta según la secuencia
    operation = process_record.operation
    
    # Números de serie que están listos para esta operación
    available_serials = SerialNumber.objects.filter(
        status__in=['IN_PROCESS', 'CREATED'],
        process_records__operation__sequence_number__lt=operation.sequence_number,
        process_records__status='APPROVED'
    ).exclude(
        # Excluir los que ya tienen esta operación completada
        process_records__operation=operation,
        process_records__status__in=['APPROVED', 'IN_PROGRESS']
    ).exclude(
        # Excluir los que tienen defectos abiertos
        defects__status__in=['OPEN', 'IN_REPAIR']
    ).distinct().select_related('authorized_part')
    
    # Si es la primera operación, incluir números de serie recién creados
    if operation.sequence_number == 1:
        first_op_serials = SerialNumber.objects.filter(
            status='CREATED'
        ).exclude(
            defects__status__in=['OPEN', 'IN_REPAIR']
        ).select_related('authorized_part')
        available_serials = available_serials.union(first_op_serials)
    
    context = {
        'process_record': process_record,
        'available_serials': available_serials,
        'operation': operation,
    }
    
    return render(request, 'manufacturing/operation_work_view.html', context)


@login_required
@operator_required
@require_POST
def assign_operation(request):
    """Asignar una operación al operador actual o a otro operador (solo supervisores/admin)"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        target_user_id = data.get('target_user_id')  # Para supervisores/admin
        
        user_role = request.user.userprofile.role
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            if process_record.assigned_operator is not None:
                return JsonResponse({
                    'success': False,
                    'message': 'Esta operación ya está asignada a otro operador.'
                })
            
            if target_user_id and user_role in ['SUPERVISOR', 'ADMIN']:
                # Supervisores/admin pueden asignar a cualquier operador
                target_user = get_object_or_404(User, id=target_user_id)
                if not hasattr(target_user, 'userprofile') or target_user.userprofile.role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
                    return JsonResponse({
                        'success': False,
                        'message': 'El usuario seleccionado no es un operador válido.'
                    })
            else:
                # Operadores solo se pueden asignar a sí mismos
                target_user = request.user
            
            existing_assignment = ProcessRecord.objects.filter(
                assigned_operator=target_user, 
                status='IN_PROGRESS'
            ).first()
            
            if existing_assignment:
                operator_name = target_user.get_full_name() or target_user.username
                return JsonResponse({
                    'success': False,
                    'message': f'{operator_name} ya tiene una operación en progreso: {existing_assignment.operation.name}. Debe completarla o liberarla primero.'
                })
            
            process_record.refresh_from_db()
            if process_record.assigned_operator is not None:
                return JsonResponse({
                    'success': False,
                    'message': 'Esta operación fue asignada a otro operador mientras procesabas la solicitud.'
                })
            
            # Asignar la operación
            process_record.assigned_operator = target_user
            process_record.status = 'IN_PROGRESS'
            process_record.started_at = timezone.now()
            process_record.assigned_at = timezone.now()
            process_record.save()
            
            # Actualizar estado del número de serie
            if process_record.serial_number.status == 'CREATED':
                process_record.serial_number.status = 'IN_PROCESS'
                process_record.serial_number.save()
            
            operator_name = target_user.get_full_name() or target_user.username
            return JsonResponse({
                'success': True,
                'message': f'Operación {process_record.operation.name} asignada exitosamente a {operator_name}.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al asignar operación: {str(e)}'
        })


@login_required
@supervisor_or_admin_required
@require_POST
def reassign_operation(request):
    """Reasignar una operación a otro operador (solo supervisores/admin)"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        new_operator_id = data.get('new_operator_id')
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            if new_operator_id:
                new_operator = get_object_or_404(User, id=new_operator_id)
                if not hasattr(new_operator, 'userprofile') or new_operator.userprofile.role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
                    return JsonResponse({
                        'success': False,
                        'message': 'El usuario seleccionado no es un operador válido.'
                    })
                
                existing_assignment = ProcessRecord.objects.filter(
                    assigned_operator=new_operator, 
                    status='IN_PROGRESS'
                ).exclude(id=process_record_id).first()
                
                if existing_assignment:
                    operator_name = new_operator.get_full_name() or new_operator.username
                    return JsonResponse({
                        'success': False,
                        'message': f'{operator_name} ya tiene una operación en progreso: {existing_assignment.operation.name}.'
                    })
                
                process_record.assigned_operator = new_operator
                process_record.assigned_at = timezone.now()
                operator_name = new_operator.get_full_name() or new_operator.username
                message = f'Operación reasignada exitosamente a {operator_name}.'
            else:
                # Liberar la operación
                process_record.assigned_operator = None
                process_record.status = 'PENDING'
                process_record.started_at = None
                process_record.assigned_at = None
                message = 'Operación liberada correctamente.'
            
            process_record.save()
            
            return JsonResponse({
                'success': True,
                'message': message
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al reasignar operación: {str(e)}'
        })


@login_required
@operator_required
@require_POST
def complete_operation(request):
    """Completar la operación para un número de serie específico"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        serial_number_id = data.get('serial_number_id')
        notes = data.get('notes', '')
        quality_passed = data.get('quality_passed', False)
        
        with transaction.atomic():
            process_record = get_object_or_404(
                ProcessRecord, 
                id=process_record_id,
                assigned_operator=request.user,
                status='IN_PROGRESS'
            )
            
            serial_number = get_object_or_404(SerialNumber, id=serial_number_id)
            
            # Crear o actualizar el registro de proceso para este número de serie específico
            specific_record, created = ProcessRecord.objects.get_or_create(
                serial_number=serial_number,
                operation=process_record.operation,
                defaults={
                    'status': 'APPROVED',
                    'processed_by': request.user,
                    'assigned_operator': request.user,
                    'started_at': timezone.now(),
                    'completed_at': timezone.now(),
                    'assigned_at': timezone.now(),
                    'notes': notes,
                    'quality_check_passed': quality_passed,
                }
            )
            
            if not created:
                # Actualizar registro existente
                specific_record.status = 'APPROVED'
                specific_record.completed_at = timezone.now()
                specific_record.processed_by = request.user
                specific_record.notes = notes
                specific_record.quality_check_passed = quality_passed
                specific_record.save()
            
            # Verificar si todas las operaciones están completadas para este número de serie
            total_operations = Operation.objects.filter(is_active=True).count()
            completed_operations = serial_number.process_records.filter(status='APPROVED').count()
            
            if completed_operations >= total_operations:
                serial_number.status = 'COMPLETED'
                serial_number.completed_at = timezone.now()
                serial_number.save()
            else:
                serial_number.status = 'IN_PROCESS'
                serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Operación {process_record.operation.name} completada para {serial_number.serial_number}.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al completar operación: {str(e)}'
        })


@login_required
@operator_required
@require_POST
def reject_serial_number(request):
    """Rechazar un número de serie y crear un defecto"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        serial_number_id = data.get('serial_number_id')
        defect_type = data.get('defect_type', 'OTHER')
        rejection_reason = data.get('rejection_reason', '')
        
        with transaction.atomic():
            process_record = get_object_or_404(
                ProcessRecord, 
                id=process_record_id,
                assigned_operator=request.user,
                status='IN_PROGRESS'
            )
            
            serial_number = get_object_or_404(SerialNumber, id=serial_number_id)
            
            # Crear el defecto
            defect = Defect.objects.create(
                serial_number=serial_number,
                operation=process_record.operation,
                defect_type=defect_type,
                description=rejection_reason,
                status='OPEN',
                reported_by=request.user
            )
            
            # Actualizar el estado del número de serie
            serial_number.status = 'DEFECTIVE'
            serial_number.save()
            
            # Crear o actualizar el registro de proceso como rechazado
            specific_record, created = ProcessRecord.objects.get_or_create(
                serial_number=serial_number,
                operation=process_record.operation,
                defaults={
                    'status': 'REJECTED',
                    'processed_by': request.user,
                    'assigned_operator': request.user,
                    'started_at': timezone.now(),
                    'completed_at': timezone.now(),
                    'assigned_at': timezone.now(),
                    'rejection_reason': rejection_reason,
                    'defect_type': defect_type,
                }
            )
            
            if not created:
                specific_record.status = 'REJECTED'
                specific_record.completed_at = timezone.now()
                specific_record.processed_by = request.user
                specific_record.rejection_reason = rejection_reason
                specific_record.defect_type = defect_type
                specific_record.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Número de serie {serial_number.serial_number} rechazado. Defecto creado: #{defect.id}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al rechazar número de serie: {str(e)}'
        })


@login_required
@operator_required
@require_POST
def release_operation(request):
    """Liberar la operación asignada al operador"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        
        with transaction.atomic():
            process_record = get_object_or_404(
                ProcessRecord, 
                id=process_record_id,
                assigned_operator=request.user,
                status='IN_PROGRESS'
            )
            
            # Liberar la operación
            process_record.assigned_operator = None
            process_record.status = 'PENDING'
            process_record.started_at = None
            process_record.assigned_at = None
            process_record.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Operación {process_record.operation.name} liberada correctamente.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al liberar operación: {str(e)}'
        })


@login_required
@operator_required
def operation_detail(request, process_record_id):
    """Vista detallada de una operación específica"""
    process_record = get_object_or_404(
        ProcessRecord, 
        id=process_record_id,
        assigned_operator=request.user,
        status='IN_PROGRESS'
    )
    
    context = {
        'process_record': process_record,
    }
    
    return render(request, 'manufacturing/operation_detail.html', context)
