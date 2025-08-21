from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth, TruncDate
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from serials.models import SerialNumber, AuthorizedPart
from operations.models import Operation, ProcessRecord
from analytics.models import ProductionAlert
from operators.models import UserProfile
from .services import SerialNumberGenerator, SerialNumberValidator
from .forms import SerialGenerationForm, LoginForm


@login_required
def dashboard(request):
    """Main dashboard view"""
    # Get recent serial numbers
    recent_serials = SerialNumber.objects.select_related(
        'authorized_part', 'created_by'
    ).order_by('-created_at')[:10]
    
    # Get statistics
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    
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
        'active_alerts': active_alerts,
        'completion_rate': round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1)
    }
    
    return render(request, 'manufacturing/dashboard.html', context)


@login_required
def generate_serial(request):
    """Generate new serial number view"""
    if request.method == 'POST':
        form = SerialGenerationForm(request.POST)
        if form.is_valid():
            try:
                # Generate serial number
                serial = SerialNumberGenerator.generate_serial_number(
                    order_number=form.cleaned_data['order_number'],
                    part_number=form.cleaned_data['authorized_part'].part_number,
                    created_by=request.user
                )
                
                messages.success(
                    request, 
                    f'Número de serie {serial.serial_number} generado exitosamente para la orden {serial.order_number}'
                )
                
                return redirect('manufacturing:manufacturing_process', serial_number=serial.serial_number)
                
            except Exception as e:
                messages.error(request, f'Error al generar número de serie: {str(e)}')
    else:
        form = SerialGenerationForm()
    
    # Get authorized parts for autocomplete
    authorized_parts = AuthorizedPart.objects.filter(is_active=True).order_by('part_number')
    
    context = {
        'form': form,
        'authorized_parts': authorized_parts
    }
    
    return render(request, 'manufacturing/generate_serial.html', context)


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
    
    return render(request, 'manufacturing/manufacturing_process.html', context)


@login_required
def summary_view(request):
    """Advanced summary view with FPY, cycle times, and detailed metrics - Admin/Supervisor only"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and 
             request.user.userprofile.role in ['ADMIN', 'SUPERVISOR'])):
        messages.error(request, 'No tienes permisos para acceder al resumen avanzado')
        return redirect('manufacturing:dashboard')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    part_filter = request.GET.get('part', '')
    order_filter = request.GET.get('order', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Build query
    serials = SerialNumber.objects.select_related(
        'authorized_part', 'created_by'
    ).prefetch_related(
        'process_records__operation',
        'process_records__assigned_operator',
        'process_records__processed_by',
        'defects'
    )
    
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
    
    # Calculate overall FPY (First Pass Yield)
    total_processes = ProcessRecord.objects.filter(status__in=['APPROVED', 'REJECTED']).count()
    first_pass_processes = ProcessRecord.objects.filter(status='APPROVED').count()
    overall_fpy = round((first_pass_processes / total_processes * 100) if total_processes > 0 else 0, 1)
    
    # Calculate FPY by operation
    operations = Operation.objects.all().order_by('sequence_number')
    operation_metrics = []
    
    for operation in operations:
        op_total = ProcessRecord.objects.filter(
            operation=operation, 
            status__in=['APPROVED', 'REJECTED']
        ).count()
        op_first_pass = ProcessRecord.objects.filter(
            operation=operation, 
            status='APPROVED'
        ).count()
        op_fpy = round((op_first_pass / op_total * 100) if op_total > 0 else 0, 1)
        
        # Calculate average cycle time for this operation
        completed_records = ProcessRecord.objects.filter(
            operation=operation,
            status='APPROVED',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        avg_cycle_time = None
        if completed_records.exists():
            cycle_times = []
            for record in completed_records:
                if record.started_at and record.completed_at:
                    cycle_time = (record.completed_at - record.started_at).total_seconds() / 60  # minutes
                    cycle_times.append(cycle_time)
            
            if cycle_times:
                avg_cycle_time = round(sum(cycle_times) / len(cycle_times), 1)
        
        # Get current operator assignments
        current_assignments = ProcessRecord.objects.filter(
            operation=operation,
            status='IN_PROGRESS',
            assigned_operator__isnull=False
        ).select_related('assigned_operator', 'serial_number')
        
        operation_metrics.append({
            'operation': operation,
            'total_processes': op_total,
            'first_pass_count': op_first_pass,
            'fpy': op_fpy,
            'avg_cycle_time': avg_cycle_time,
            'current_assignments': current_assignments,
            'available_count': ProcessRecord.objects.filter(
                operation=operation,
                status='PENDING',
                assigned_operator__isnull=True
            ).count()
        })
    
    detailed_serials = []
    for serial in serials:
        # Get current operation (next pending or in progress)
        current_process = serial.process_records.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).order_by('operation__sequence_number').first()
        
        # Calculate completion percentage
        total_operations = serial.process_records.count()
        completed_operations = serial.process_records.filter(status='APPROVED').count()
        completion_percentage = round((completed_operations / total_operations * 100) if total_operations > 0 else 0, 1)
        
        # Get defects count
        defects_count = serial.defects.filter(status__in=['OPEN', 'IN_REPAIR']).count()
        
        # Calculate total cycle time for completed operations
        total_cycle_time = 0
        completed_processes = serial.process_records.filter(
            status='APPROVED',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        for process in completed_processes:
            if process.started_at and process.completed_at:
                cycle_time = (process.completed_at - process.started_at).total_seconds() / 60
                total_cycle_time += cycle_time
        
        detailed_serials.append({
            'serial': serial,
            'current_process': current_process,
            'completion_percentage': completion_percentage,
            'defects_count': defects_count,
            'total_cycle_time': round(total_cycle_time, 1) if total_cycle_time > 0 else None,
            'all_processes': serial.process_records.all().order_by('operation__sequence_number')
        })
    
    # Pagination
    paginator = Paginator(detailed_serials, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = SerialNumber.STATUS_CHOICES
    authorized_parts = AuthorizedPart.objects.filter(is_active=True).order_by('part_number')
    
    total_serials_count = serials.count()
    completed_count = serials.filter(status='COMPLETED').count()
    in_process_count = serials.filter(status='IN_PROCESS').count()
    pending_count = serials.filter(status='CREATED').count()
    failed_count = serials.filter(status='FAILED').count()
    
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
        'overall_fpy': overall_fpy,
        'operation_metrics': operation_metrics,
        'summary_stats': {
            'total_serials': total_serials_count,
            'completed': completed_count,
            'in_process': in_process_count,
            'pending': pending_count,
            'failed': failed_count,
            'completion_rate': round((completed_count / total_serials_count * 100) if total_serials_count > 0 else 0, 1)
        }
    }
    
    return render(request, 'manufacturing/summary.html', context)


@login_required
def admin_panel(request):
    """Admin panel for managing operations, users, and serial numbers"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_manage_users)):
        messages.error(request, 'No tienes permisos para acceder al panel de administración')
        return redirect('manufacturing:dashboard')
    
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
    
    return render(request, 'manufacturing/admin_panel.html', context)


@login_required
def statistics_view(request):
    """Statistics and charts view"""
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'userprofile') and request.user.userprofile.can_view_statistics)):
        messages.error(request, 'No tienes permisos para ver las estadísticas')
        return redirect('manufacturing:dashboard')
    
    from datetime import datetime, timedelta
    
    # Basic statistics
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    completion_rate = round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1)
    
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
    end_date = datetime.now().date()
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
    
    context = {
        'total_serials': total_serials,
        'completed_serials': completed_serials,
        'in_process_serials': in_process_serials,
        'pending_serials': pending_serials,
        'completion_rate': completion_rate,
        'operations_labels': json.dumps(operations_labels),
        'operations_completed': json.dumps(operations_completed),
        'operations_pending': json.dumps(operations_pending),
        'production_dates': json.dumps(production_dates),
        'production_counts': json.dumps(production_counts),
        'alerts': alerts,
    }
    
    return render(request, 'manufacturing/statistics.html', context)


def login_view(request):
    """Login view"""
    if request.user.is_authenticated:
        return redirect('manufacturing:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'manufacturing:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Usuario o contraseña incorrectos')
    else:
        form = LoginForm()
    
    return render(request, 'manufacturing/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('manufacturing:login')


# AJAX Views for dynamic functionality
@login_required
@require_http_methods(["GET"])
def get_authorized_parts(request):
    """AJAX endpoint to get authorized parts for autocomplete"""
    query = request.GET.get('q', '')
    
    parts = AuthorizedPart.objects.filter(
        is_active=True,
        part_number__icontains=query
    ).order_by('part_number')[:10]
    
    data = [
        {
            'id': part.id,
            'part_number': part.part_number,
            'description': part.description,
            'revision': part.revision
        }
        for part in parts
    ]
    
    return JsonResponse({'parts': data})


@login_required
@require_http_methods(["POST"])
def validate_order_number(request):
    """AJAX endpoint to validate order number"""
    data = json.loads(request.body)
    order_number = data.get('order_number', '')
    
    try:
        SerialNumberValidator.validate_order_number(order_number)
        has_duplicates = SerialNumberValidator.check_order_duplicates(order_number)
        
        return JsonResponse({
            'valid': True,
            'has_duplicates': has_duplicates,
            'message': 'Número de orden válido' if not has_duplicates else 'Este número de orden ya tiene números de serie asociados'
        })
    except Exception as e:
        return JsonResponse({
            'valid': False,
            'message': str(e)
        })


@login_required
@require_http_methods(["GET"])
def api_statistics(request):
    """API endpoint for statistics data"""
    total_serials = SerialNumber.objects.count()
    completed_serials = SerialNumber.objects.filter(status='COMPLETED').count()
    in_process_serials = SerialNumber.objects.filter(status='IN_PROCESS').count()
    pending_serials = SerialNumber.objects.filter(status='CREATED').count()
    completion_rate = round((completed_serials / total_serials * 100) if total_serials > 0 else 0, 1)
    
    return JsonResponse({
        'total_serials': total_serials,
        'completed_serials': completed_serials,
        'in_process_serials': in_process_serials,
        'pending_serials': pending_serials,
        'completion_rate': completion_rate,
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
