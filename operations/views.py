from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from serials.models import SerialNumber, AuthorizedPart
from analytics.models import ProductionAlert
from operators.models import UserProfile
from .models import ProcessRecord, Operation
import json


@login_required
def manufacturing_process(request, serial_number):
    """Manufacturing process tracking view"""
    serial = get_object_or_404(SerialNumber, serial_number=serial_number)
    
    # Get process records with operations
    process_records = ProcessRecord.objects.filter(
        serial_number=serial
    ).select_related('operation', 'processed_by').order_by('operation__sequence_number')
    
    # Get current operation (next to be processed)
    current_operation = serial.current_operation
    
    context = {
        'serial': serial,
        'process_records': process_records,
        'current_operation': current_operation,
        'can_approve': request.user.userprofile.can_approve_operations if hasattr(request.user, 'userprofile') else False
    }
    
    return render(request, 'operations/manufacturing_process.html', context)


@login_required
def summary_view(request):
    """Summary view with operations data and assignment functionality"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    part_filter = request.GET.get('part', '')
    order_filter = request.GET.get('order', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Build query
    serials = SerialNumber.objects.select_related(
        'authorized_part', 'created_by'
    ).prefetch_related('process_records__operation')
    
    if status_filter:
        serials = serials.filter(status=status_filter)
    
    if part_filter:
        serials = serials.filter(authorized_part__part_number__icontains=part_filter)
    
    if order_filter:
        serials = serials.filter(order_number__icontains=order_filter)
    
    if date_from:
        serials = serials.filter(created_at__date__gte=date_from)
    
    if date_to:
        serials = serials.filter(created_at__date__lte=date_to)
    
    # Order by creation date (newest first)
    serials = serials.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(serials, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = SerialNumber.STATUS_CHOICES
    authorized_parts = AuthorizedPart.objects.filter(is_active=True).order_by('part_number')
    
    # Get all operations with their current assignments and availability
    operations = Operation.objects.filter(is_active=True).order_by('sequence_number')
    
    operations_data = []
    for operation in operations:
        # Get current process records for this operation that are in progress
        current_assignments = ProcessRecord.objects.filter(
            operation=operation,
            status='IN_PROGRESS'
        ).select_related('assigned_operator', 'serial_number')
        
        # Count free operations (pending without assigned operator)
        free_operations_count = ProcessRecord.objects.filter(
            operation=operation,
            status='PENDING',
            assigned_operator__isnull=True
        ).count()
        
        # Get assigned operator (if any)
        assigned_operator = None
        serial_number = None
        if current_assignments.exists():
            first_assignment = current_assignments.first()
            assigned_operator = first_assignment.assigned_operator
            serial_number = first_assignment.serial_number
        
        # Determine if operation is available for assignment
        is_available = free_operations_count > 0
        
        operations_data.append({
            'operation': operation,
            'assigned_operator': assigned_operator,
            'serial_number': serial_number,
            'free_operations_count': free_operations_count,
            'is_available': is_available,
        })
    
    # Check if user can change operators (admin or supervisor)
    user_can_change_operator = (
        request.user.is_superuser or 
        (hasattr(request.user, 'userprofile') and 
         request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])
    )
    
    # Get available operators for the change operator modal
    available_operators = UserProfile.objects.filter(
        role__in=['OPERATOR', 'SUPERVISOR', 'ADMIN'],
        user__is_active=True
    ).select_related('user')
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'authorized_parts': authorized_parts,
        'current_filters': {
            'status': status_filter,
            'part': part_filter,
            'order': order_filter,
            'date_from': date_from,
            'date_to': date_to,
        },
        'operations_data': operations_data,
        'user_can_change_operator': user_can_change_operator,
        'available_operators': available_operators,
    }
    
    return render(request, 'operations/summary.html', context)


@login_required
def admin_panel(request):
    """Admin panel for managing operations, users, and serial numbers"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_manage_users)):
        messages.error(request, 'No tienes permisos para acceder al panel de administración')
        return redirect('analytics:dashboard')
    
    # Get counts for dashboard
    total_users = UserProfile.objects.count()
    total_operations = Operation.objects.count()
    total_parts = AuthorizedPart.objects.count()
    active_alerts = ProductionAlert.objects.filter(is_active=True, is_resolved=False).count()
    
    context = {
        'total_users': total_users,
        'total_operations': total_operations,
        'total_parts': total_parts,
        'active_alerts': active_alerts,
    }
    
    return render(request, 'operations/admin_panel.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def manage_users(request):
    """API endpoint for user management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_manage_users)):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    if request.method == 'GET':
        users = User.objects.select_related('userprofile').all()
        users_data = []
        for user in users:
            profile = getattr(user, 'userprofile', None)
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'role': profile.role if profile else 'OPERATOR',
                'can_approve_operations': profile.can_approve_operations if profile else False,
                'can_manage_users': profile.can_manage_users if profile else False,
            })
        return JsonResponse({'users': users_data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                password=data.get('password', 'temp123')
            )
            
            # Create or update profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = data.get('role', 'OPERATOR')
            profile.can_approve_operations = data.get('can_approve_operations', False)
            profile.can_manage_users = data.get('can_manage_users', False)
            profile.save()
            
            return JsonResponse({'success': True, 'message': 'Usuario creado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["PUT", "DELETE"])
def manage_user(request, user_id):
    """API endpoint for individual user management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_manage_users)):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            user.username = data.get('username', user.username)
            user.email = data.get('email', user.email)
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.is_active = data.get('is_active', user.is_active)
            user.save()
            
            # Update profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = data.get('role', profile.role)
            profile.can_approve_operations = data.get('can_approve_operations', profile.can_approve_operations)
            profile.can_manage_users = data.get('can_manage_users', profile.can_manage_users)
            profile.save()
            
            return JsonResponse({'success': True, 'message': 'Usuario actualizado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        try:
            user.is_active = False
            user.save()
            return JsonResponse({'success': True, 'message': 'Usuario desactivado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def manage_operations(request):
    """API endpoint for operations management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    if request.method == 'GET':
        operations = Operation.objects.all().order_by('sequence_number')
        operations_data = []
        for operation in operations:
            operations_data.append({
                'id': operation.id,
                'name': operation.name,
                'description': operation.description,
                'sequence_number': operation.sequence_number,
                'estimated_time_minutes': operation.estimated_time_minutes,
                'requires_approval': operation.requires_approval,
                'is_active': operation.is_active,
            })
        return JsonResponse({'operations': operations_data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            operation = Operation.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                sequence_number=data['sequence_number'],
                estimated_time_minutes=data.get('estimated_time_minutes', 30),
                requires_approval=data.get('requires_approval', True),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'message': 'Operación creada exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["PUT", "DELETE"])
def manage_operation(request, operation_id):
    """API endpoint for individual operation management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    operation = get_object_or_404(Operation, id=operation_id)
    
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            operation.name = data.get('name', operation.name)
            operation.description = data.get('description', operation.description)
            operation.sequence_number = data.get('sequence_number', operation.sequence_number)
            operation.estimated_time_minutes = data.get('estimated_time_minutes', operation.estimated_time_minutes)
            operation.requires_approval = data.get('requires_approval', operation.requires_approval)
            operation.is_active = data.get('is_active', operation.is_active)
            operation.save()
            
            return JsonResponse({'success': True, 'message': 'Operación actualizada exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        try:
            operation.is_active = False
            operation.save()
            return JsonResponse({'success': True, 'message': 'Operación desactivada exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def manage_parts(request):
    """API endpoint for parts management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    if request.method == 'GET':
        parts = AuthorizedPart.objects.all().order_by('part_number')
        parts_data = []
        for part in parts:
            parts_data.append({
                'id': part.id,
                'part_number': part.part_number,
                'description': part.description,
                'revision': part.revision,
                'is_active': part.is_active,
                'created_at': part.created_at.isoformat(),
            })
        return JsonResponse({'parts': parts_data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            part = AuthorizedPart.objects.create(
                part_number=data['part_number'],
                description=data['description'],
                revision=data.get('revision', 'A'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'success': True, 'message': 'Componente creado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["PUT", "DELETE"])
def manage_part(request, part_id):
    """API endpoint for individual part management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    part = get_object_or_404(AuthorizedPart, id=part_id)
    
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            part.part_number = data.get('part_number', part.part_number)
            part.description = data.get('description', part.description)
            part.revision = data.get('revision', part.revision)
            part.is_active = data.get('is_active', part.is_active)
            part.save()
            
            return JsonResponse({'success': True, 'message': 'Componente actualizado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        try:
            part.is_active = False
            part.save()
            return JsonResponse({'success': True, 'message': 'Componente desactivado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def manage_serials(request):
    """API endpoint for serial numbers management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    serials = SerialNumber.objects.select_related('authorized_part', 'created_by').all()
    serials_data = []
    for serial in serials:
        serials_data.append({
            'id': serial.id,
            'serial_number': serial.serial_number,
            'order_number': serial.order_number,
            'part_number': serial.authorized_part.part_number,
            'status': serial.status,
            'completion_percentage': serial.completion_percentage,
            'created_by': serial.created_by.username,
            'created_at': serial.created_at.isoformat(),
        })
    return JsonResponse({'serials': serials_data})


@login_required
@require_http_methods(["PUT", "DELETE"])
def manage_serial(request, serial_id):
    """API endpoint for individual serial management"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    
    serial = get_object_or_404(SerialNumber, id=serial_id)
    
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            serial.order_number = data.get('order_number', serial.order_number)
            serial.status = data.get('status', serial.status)
            serial.save()
            
            return JsonResponse({'success': True, 'message': 'Número de serie actualizado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        try:
            serial.delete()
            return JsonResponse({'success': True, 'message': 'Número de serie eliminado exitosamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
