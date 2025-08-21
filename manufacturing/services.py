from django.db import transaction
from django.core.exceptions import ValidationError
from serials.models import SerialNumber, AuthorizedPart
from operations.models import ProcessRecord, Operation
from analytics.models import ProductionAlert
import re
from django.utils import timezone


class SerialNumberGenerator:
    """Service class for generating serial numbers with KM###W###R format"""
    
    @staticmethod
    def get_next_serial_number():
        """Generate the next available serial number in KM###W###R format"""
        
        # Get the last serial number to determine the next sequence
        last_serial = SerialNumber.objects.order_by('-serial_number').first()
        
        if not last_serial:
            # First serial number
            return "KM001W001R"
        
        # Extract numbers from the last serial number
        pattern = r'KM(\d{3})W(\d{3})R'
        match = re.match(pattern, last_serial.serial_number)
        
        if not match:
            # Fallback if pattern doesn't match
            return "KM001W001R"
        
        first_part = int(match.group(1))
        second_part = int(match.group(2))
        
        # Increment logic: increment second part first, then first part
        second_part += 1
        
        if second_part > 999:
            second_part = 1
            first_part += 1
            
        if first_part > 999:
            raise ValidationError("Se ha alcanzado el límite máximo de números de serie")
        
        return f"KM{first_part:03d}W{second_part:03d}R"
    
    @staticmethod
    @transaction.atomic
    def generate_serial_number(order_number, part_number, created_by):
        """
        Generate a new serial number for the given order and part
        
        Args:
            order_number (str): Order number to associate with the serial
            part_number (str): Part number from authorized parts
            created_by (User): User creating the serial number
            
        Returns:
            SerialNumber: The created serial number instance
            
        Raises:
            ValidationError: If part is not authorized or other validation errors
        """
        
        # Validate authorized part
        try:
            authorized_part = AuthorizedPart.objects.get(
                part_number=part_number,
                is_active=True
            )
        except AuthorizedPart.DoesNotExist:
            raise ValidationError(f"El número de parte '{part_number}' no está autorizado")
        
        # Generate next serial number
        serial_number = SerialNumberGenerator.get_next_serial_number()
        
        # Ensure uniqueness (double-check)
        max_attempts = 100
        attempts = 0
        
        while SerialNumber.objects.filter(serial_number=serial_number).exists():
            attempts += 1
            if attempts >= max_attempts:
                raise ValidationError("No se pudo generar un número de serie único")
            
            # Try to get next number
            last_serial = SerialNumber.objects.order_by('-serial_number').first()
            pattern = r'KM(\d{3})W(\d{3})R'
            match = re.match(pattern, last_serial.serial_number)
            
            if match:
                first_part = int(match.group(1))
                second_part = int(match.group(2)) + attempts
                
                if second_part > 999:
                    second_part = second_part % 1000
                    first_part += 1
                
                serial_number = f"KM{first_part:03d}W{second_part:03d}R"
        
        # Create the serial number
        serial_instance = SerialNumber.objects.create(
            serial_number=serial_number,
            order_number=order_number,
            authorized_part=authorized_part,
            created_by=created_by,
            status='CREATED'
        )
        
        return serial_instance
    
    @staticmethod
    def validate_serial_format(serial_number):
        """Validate that a serial number follows the KM###W###R format"""
        pattern = r'^KM\d{3}W\d{3}R$'
        return bool(re.match(pattern, serial_number))
    
    @staticmethod
    def get_serial_info(serial_number):
        """Extract information from a serial number"""
        pattern = r'KM(\d{3})W(\d{3})R'
        match = re.match(pattern, serial_number)
        
        if not match:
            return None
        
        return {
            'first_sequence': int(match.group(1)),
            'second_sequence': int(match.group(2)),
            'full_number': serial_number
        }


class SerialNumberValidator:
    """Validation utilities for serial numbers"""
    
    @staticmethod
    def validate_order_number(order_number):
        """Validate order number format and requirements"""
        if not order_number or len(order_number.strip()) == 0:
            raise ValidationError("El número de orden es requerido")
        
        if len(order_number) > 50:
            raise ValidationError("El número de orden no puede exceder 50 caracteres")
        
        # Check for valid characters (alphanumeric, hyphens, underscores)
        if not re.match(r'^[A-Za-z0-9\-_]+$', order_number):
            raise ValidationError("El número de orden solo puede contener letras, números, guiones y guiones bajos")
        
        return True
    
    @staticmethod
    def check_order_duplicates(order_number, exclude_serial=None):
        """Check if order number already has associated serial numbers"""
        query = SerialNumber.objects.filter(order_number=order_number)
        
        if exclude_serial:
            query = query.exclude(pk=exclude_serial.pk)
        
        return query.exists()
    
    @staticmethod
    def validate_part_availability(part_number):
        """Validate that a part number is available for use"""
        try:
            part = AuthorizedPart.objects.get(part_number=part_number)
            if not part.is_active:
                raise ValidationError(f"El componente '{part_number}' no está activo")
            return part
        except AuthorizedPart.DoesNotExist:
            raise ValidationError(f"El componente '{part_number}' no está autorizado")


class SerialNumberBulkGenerator:
    """Service for generating multiple serial numbers at once"""
    
    @staticmethod
    @transaction.atomic
    def generate_bulk_serials(order_number, part_number, quantity, created_by):
        """
        Generate multiple serial numbers for the same order and part
        
        Args:
            order_number (str): Order number
            part_number (str): Part number
            quantity (int): Number of serials to generate
            created_by (User): User creating the serials
            
        Returns:
            list: List of created SerialNumber instances
        """
        
        if quantity <= 0 or quantity > 100:
            raise ValidationError("La cantidad debe estar entre 1 y 100")
        
        # Validate part
        SerialNumberValidator.validate_part_availability(part_number)
        SerialNumberValidator.validate_order_number(order_number)
        
        created_serials = []
        
        for i in range(quantity):
            try:
                serial = SerialNumberGenerator.generate_serial_number(
                    order_number=f"{order_number}-{i+1:03d}",
                    part_number=part_number,
                    created_by=created_by
                )
                created_serials.append(serial)
            except ValidationError as e:
                # If we fail partway through, we need to clean up
                # The transaction will be rolled back automatically
                raise ValidationError(f"Error generando serie {i+1}: {str(e)}")
        
        return created_serials


class ManufacturingProcessService:
    """Service class for managing manufacturing process operations"""
    
    @staticmethod
    @transaction.atomic
    def process_operation(serial, operation, action, user, notes="", quality_check_passed=False):
        """
        Process a manufacturing operation
        
        Args:
            serial (SerialNumber): Serial number instance
            operation (Operation): Operation to process
            action (str): Action to perform ('start', 'approve', 'reject')
            user (User): User performing the action
            notes (str): Additional notes
            quality_check_passed (bool): Quality check status
            
        Returns:
            dict: Result with process_record and message
        """
        
        # Get or create process record
        process_record, created = ProcessRecord.objects.get_or_create(
            serial_number=serial,
            operation=operation,
            defaults={
                'status': 'PENDING',
                'notes': notes
            }
        )
        
        # Validate operation sequence
        if not ManufacturingProcessService._validate_operation_sequence(serial, operation):
            raise ValidationError(
                f"No se puede procesar la operación {operation.name}. "
                "Debe completar las operaciones anteriores primero."
            )
        
        # Process based on action
        if action == 'start':
            if process_record.status != 'PENDING':
                raise ValidationError("Esta operación ya ha sido iniciada")
            
            process_record.status = 'IN_PROGRESS'
            process_record.started_at = timezone.now()
            process_record.processed_by = user
            message = f"Operación {operation.name} iniciada"
            
        elif action == 'approve':
            if process_record.status not in ['IN_PROGRESS', 'PENDING']:
                raise ValidationError("Esta operación no puede ser aprobada en su estado actual")
            
            process_record.status = 'APPROVED'
            process_record.completed_at = timezone.now()
            process_record.processed_by = user
            process_record.quality_check_passed = quality_check_passed
            message = f"Operación {operation.name} aprobada"
            
        elif action == 'reject':
            if process_record.status == 'APPROVED':
                raise ValidationError("No se puede rechazar una operación ya aprobada")
            
            process_record.status = 'REJECTED'
            process_record.completed_at = timezone.now()
            process_record.processed_by = user
            message = f"Operación {operation.name} rechazada"
            
        else:
            raise ValidationError("Acción no válida")
        
        # Update notes
        if notes:
            process_record.notes = notes
        
        process_record.save()
        
        # Send real-time notification
        from .utils import NotificationService
        NotificationService.send_process_notification(
            serial_number=serial.serial_number,
            operation=operation.name,
            status=process_record.status,
            user=user.get_full_name()
        )
        
        # Check if all operations are completed and update serial status
        ManufacturingProcessService._update_serial_status(serial)
        
        return {
            'process_record': process_record,
            'message': message
        }
    
    @staticmethod
    def _validate_operation_sequence(serial, operation):
        """Validate that operations are processed in correct sequence"""
        
        # Get all previous operations
        previous_operations = Operation.objects.filter(
            is_active=True,
            sequence_number__lt=operation.sequence_number
        )
        
        # Check if all previous operations are approved
        for prev_op in previous_operations:
            try:
                prev_record = ProcessRecord.objects.get(
                    serial_number=serial,
                    operation=prev_op
                )
                if prev_record.status != 'APPROVED':
                    return False
            except ProcessRecord.DoesNotExist:
                return False
        
        return True
    
    @staticmethod
    def _update_serial_status(serial):
        """Update serial number status based on process records"""
        
        total_operations = Operation.objects.filter(is_active=True).count()
        approved_operations = ProcessRecord.objects.filter(
            serial_number=serial,
            status='APPROVED'
        ).count()
        rejected_operations = ProcessRecord.objects.filter(
            serial_number=serial,
            status='REJECTED'
        ).count()
        
        if rejected_operations > 0:
            serial.status = 'REJECTED'
        elif approved_operations == total_operations:
            serial.status = 'COMPLETED'
            serial.completed_at = timezone.now()
        elif approved_operations > 0:
            serial.status = 'IN_PROCESS'
        else:
            serial.status = 'CREATED'
        
        serial.save()
    
    @staticmethod
    def get_operation_history(serial):
        """Get complete operation history for a serial number"""
        
        return ProcessRecord.objects.filter(
            serial_number=serial
        ).select_related(
            'operation', 'processed_by'
        ).order_by('operation__sequence_number')
    
    @staticmethod
    def get_pending_operations(user=None):
        """Get operations pending approval"""
        
        query = ProcessRecord.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).select_related(
            'serial_number', 'operation', 'processed_by'
        ).order_by('created_at')
        
        if user and hasattr(user, 'userprofile'):
            # Filter based on user permissions or department
            if not user.userprofile.can_approve_operations:
                query = query.filter(processed_by=user)
        
        return query
    
    @staticmethod
    def create_production_alert(title, message, alert_type, priority, serial_number=None, created_by=None):
        """Create a production alert"""
        
        alert = ProductionAlert.objects.create(
            title=title,
            message=message,
            alert_type=alert_type,
            priority=priority,
            serial_number=serial_number,
            created_by=created_by
        )
        
        # Send real-time notification
        from .utils import NotificationService
        NotificationService.send_alert_notification(
            alert_type=alert_type,
            message=f"{title}: {message}",
            priority=priority
        )
        
        return alert
