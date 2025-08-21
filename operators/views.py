from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from operations.models import ProcessRecord, Operation
from serials.models import SerialNumber
from defects.models import Defect
from .models import UserProfile
from .decorators import operator_required, supervisor_or_admin_required
from .forms import LoginForm
import json


def login_view(request):
    """Login view"""
    if request.user.is_authenticated:
        return redirect('analytics:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'analytics:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Usuario o contraseña incorrectos')
    else:
        form = LoginForm()
    
    return render(request, 'operators/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('operators:login')


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
        # Operadores solo ven operaciones sin asignar
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
    
    return render(request, 'operators/operator_dashboard.html', context)


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
    
    operation = process_record.operation
    
    available_serials = SerialNumber.objects.filter(
        status__in=['IN_PROCESS', 'CREATED'],
        process_records__operation__sequence_number__lt=operation.sequence_number,
        process_records__status='APPROVED'
    ).exclude(
        process_records__operation=operation,
        process_records__status__in=['APPROVED', 'IN_PROGRESS']
    ).exclude(
        defects__status__in=['OPEN', 'IN_REPAIR']
    ).distinct().select_related('authorized_part').order_by()  # Clear any default ordering
    
    if operation.sequence_number == 1:
        first_op_serials = SerialNumber.objects.filter(
            status='CREATED'
        ).exclude(
            defects__status__in=['OPEN', 'IN_REPAIR']
        ).select_related('authorized_part').order_by()  # Clear any default ordering
        
        available_serials = available_serials.union(first_op_serials).order_by('serial_number')
    else:
        available_serials = available_serials.order_by('serial_number')
    
    context = {
        'process_record': process_record,
        'available_serials': available_serials,
        'operation': operation,
    }
    
    return render(request, 'operators/operation_work_view.html', context)


@login_required
@operator_required
@require_POST
def assign_operation(request):
    """Asignar una operación al operador actual o a otro operador (solo supervisores/admin)"""
    try:
        data = json.loads(request.body)
        process_record_id = data.get('process_record_id')
        target_user_id = data.get('target_user_id')
        
        user_role = request.user.userprofile.role
        
        with transaction.atomic():
            process_record = get_object_or_404(ProcessRecord, id=process_record_id)
            
            if target_user_id and user_role in ['SUPERVISOR', 'ADMIN']:
                target_user = get_object_or_404(User, id=target_user_id)
                if not hasattr(target_user, 'userprofile') or target_user.userprofile.role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
                    return JsonResponse({
                        'success': False,
                        'message': 'El usuario seleccionado no es un operador válido.'
                    })
            else:
                target_user = request.user
            
            if user_role == 'OPERATOR':
                if process_record.assigned_operator is not None:
                    return JsonResponse({
                        'success': False,
                        'message': 'Esta operación ya está asignada a otro operador.'
                    })
                
                if ProcessRecord.objects.filter(assigned_operator=target_user, status='IN_PROGRESS').exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Ya tienes una operación en progreso. Complétala o libérala primero.'
                    })
            
            process_record.assigned_operator = target_user
            process_record.status = 'IN_PROGRESS'
            process_record.started_at = timezone.now()
            process_record.assigned_at = timezone.now()
            process_record.save()
            
            if process_record.serial_number.status == 'CREATED':
                process_record.serial_number.status = 'IN_PROCESS'
                process_record.serial_number.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Operación {process_record.operation.name} asignada a {target_user.get_full_name() or target_user.username}.'
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
                
                if new_operator.userprofile.role == 'OPERATOR' and ProcessRecord.objects.filter(assigned_operator=new_operator, status='IN_PROGRESS').exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'El operador seleccionado ya tiene una operación en progreso.'
                    })
                
                process_record.assigned_operator = new_operator
                process_record.assigned_at = timezone.now()
                message = f'Operación reasignada a {new_operator.get_full_name() or new_operator.username}.'
            else:
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
                specific_record.status = 'APPROVED'
                specific_record.completed_at = timezone.now()
                specific_record.processed_by = request.user
                specific_record.notes = notes
                specific_record.quality_check_passed = quality_passed
                specific_record.save()
            
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
            
            defect = Defect.objects.create(
                serial_number=serial_number,
                operation=process_record.operation,
                defect_type=defect_type,
                description=rejection_reason,
                status='OPEN',
                reported_by=request.user
            )
            
            serial_number.status = 'DEFECTIVE'
            serial_number.save()
            
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
    
    return render(request, 'operators/operation_detail.html', context)
