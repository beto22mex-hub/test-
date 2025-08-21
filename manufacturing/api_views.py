from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
import json

from serials.models import SerialNumber, AuthorizedPart
from operations.models import Operation, ProcessRecord
from analytics.models import ProductionAlert
from .serializers import (
    SerialNumberSerializer, OperationSerializer, 
    ProcessRecordSerializer, AuthorizedPartSerializer
)
from .services import SerialNumberGenerator, ManufacturingProcessService
from .utils import ExportUtils


class SerialNumberViewSet(viewsets.ModelViewSet):
    """ViewSet for SerialNumber CRUD operations"""
    queryset = SerialNumber.objects.all()
    serializer_class = SerialNumberSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = SerialNumber.objects.select_related(
            'authorized_part', 'created_by'
        ).prefetch_related('process_records__operation')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by part
        part_filter = self.request.query_params.get('part', None)
        if part_filter:
            queryset = queryset.filter(authorized_part__part_number__icontains=part_filter)
        
        # Filter by order
        order_filter = self.request.query_params.get('order', None)
        if order_filter:
            queryset = queryset.filter(order_number__icontains=order_filter)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['get'])
    def process_status(self, request, pk=None):
        """Get detailed process status for a serial number"""
        serial = self.get_object()
        process_records = ProcessRecord.objects.filter(
            serial_number=serial
        ).select_related('operation', 'processed_by').order_by('operation__sequence_number')
        
        data = {
            'serial_number': serial.serial_number,
            'status': serial.status,
            'completion_percentage': serial.completion_percentage,
            'current_operation': serial.current_operation.name if serial.current_operation else None,
            'process_records': ProcessRecordSerializer(process_records, many=True).data
        }
        
        return Response(data)


class OperationViewSet(viewsets.ModelViewSet):
    """ViewSet for Operation CRUD operations"""
    queryset = Operation.objects.all()
    serializer_class = OperationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Operation.objects.filter(is_active=True).order_by('sequence_number')


class AuthorizedPartViewSet(viewsets.ModelViewSet):
    """ViewSet for AuthorizedPart CRUD operations"""
    queryset = AuthorizedPart.objects.all()
    serializer_class = AuthorizedPartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = AuthorizedPart.objects.all()
        
        # Filter by active status
        active_only = self.request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('part_number')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_serial_api(request):
    """API endpoint to generate serial numbers"""
    try:
        data = request.data
        order_number = data.get('order_number')
        part_number = data.get('part_number')
        quantity = data.get('quantity', 1)
        
        if not order_number or not part_number:
            return Response(
                {'error': 'order_number y part_number son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate serial numbers
        if quantity == 1:
            serial = SerialNumberGenerator.generate_serial_number(
                order_number=order_number,
                part_number=part_number,
                created_by=request.user
            )
            return Response({
                'success': True,
                'serial_number': serial.serial_number,
                'message': f'Número de serie {serial.serial_number} generado exitosamente'
            })
        else:
            from .services import SerialNumberBulkGenerator
            serials = SerialNumberBulkGenerator.generate_bulk_serials(
                order_number=order_number,
                part_number=part_number,
                quantity=int(quantity),
                created_by=request.user
            )
            return Response({
                'success': True,
                'serial_numbers': [s.serial_number for s in serials],
                'message': f'{len(serials)} números de serie generados exitosamente'
            })
            
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Error interno: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_operation_api(request):
    """API endpoint to process manufacturing operations"""
    try:
        data = request.data
        serial_number = data.get('serial_number')
        operation_id = data.get('operation_id')
        action = data.get('action')  # 'start', 'approve', 'reject'
        username = data.get('username')
        password = data.get('password')
        notes = data.get('notes', '')
        quality_check = data.get('quality_check_passed', False)
        
        # Validate required fields
        if not all([serial_number, operation_id, action, username, password]):
            return Response(
                {'error': 'Todos los campos son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Authenticate user for operation approval
        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {'error': 'Credenciales incorrectas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user can approve operations
        if action in ['approve', 'reject'] and not user.userprofile.can_approve_operations:
            return Response(
                {'error': 'No tienes permisos para aprobar operaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get serial and operation
        serial = get_object_or_404(SerialNumber, serial_number=serial_number)
        operation = get_object_or_404(Operation, id=operation_id)
        
        # Process the operation
        result = ManufacturingProcessService.process_operation(
            serial=serial,
            operation=operation,
            action=action,
            user=user,
            notes=notes,
            quality_check_passed=quality_check
        )
        
        return Response({
            'success': True,
            'message': result['message'],
            'process_record': ProcessRecordSerializer(result['process_record']).data
        })
        
    except ValidationError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Error procesando operación: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_excel(request):
    """Export serial numbers to Excel"""
    try:
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        part_filter = request.GET.get('part', '')
        order_filter = request.GET.get('order', '')
        
        # Build queryset
        queryset = SerialNumber.objects.select_related(
            'authorized_part', 'created_by'
        ).prefetch_related('process_records__operation')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if part_filter:
            queryset = queryset.filter(authorized_part__part_number__icontains=part_filter)
        if order_filter:
            queryset = queryset.filter(order_number__icontains=order_filter)
        
        # Generate Excel file
        response = ExportUtils.export_to_excel(queryset)
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Error exportando a Excel: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_pdf(request):
    """Export serial numbers to PDF"""
    try:
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        part_filter = request.GET.get('part', '')
        order_filter = request.GET.get('order', '')
        
        # Build queryset
        queryset = SerialNumber.objects.select_related(
            'authorized_part', 'created_by'
        ).prefetch_related('process_records__operation')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if part_filter:
            queryset = queryset.filter(authorized_part__part_number__icontains=part_filter)
        if order_filter:
            queryset = queryset.filter(order_number__icontains=order_filter)
        
        # Generate PDF file
        response = ExportUtils.export_to_pdf(queryset)
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Error exportando a PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistics_api(request):
    """API endpoint for statistics data"""
    try:
        from django.db.models import Count, Avg, Q
        from django.db.models.functions import TruncDate, TruncMonth
        
        # Production statistics
        production_stats = SerialNumber.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Parts usage
        parts_stats = SerialNumber.objects.values(
            'authorized_part__part_number',
            'authorized_part__description'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        
        # Daily production (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        daily_production = SerialNumber.objects.filter(
            created_at__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Operation performance
        operation_stats = ProcessRecord.objects.filter(
            status='APPROVED'
        ).values(
            'operation__name'
        ).annotate(
            count=Count('id'),
            avg_time=Avg('completed_at') - Avg('started_at')
        ).order_by('operation__sequence_number')
        
        # Quality metrics
        quality_stats = ProcessRecord.objects.filter(
            status='APPROVED'
        ).aggregate(
            total_approved=Count('id'),
            quality_passed=Count('id', filter=Q(quality_check_passed=True))
        )
        
        quality_rate = 0
        if quality_stats['total_approved'] > 0:
            quality_rate = (quality_stats['quality_passed'] / quality_stats['total_approved']) * 100
        
        return Response({
            'production_stats': list(production_stats),
            'parts_stats': list(parts_stats),
            'daily_production': list(daily_production),
            'operation_stats': list(operation_stats),
            'quality_rate': round(quality_rate, 2),
            'total_serials': SerialNumber.objects.count(),
            'active_alerts': ProductionAlert.objects.filter(
                is_active=True, is_resolved=False
            ).count()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error obteniendo estadísticas: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
