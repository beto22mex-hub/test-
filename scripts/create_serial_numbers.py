#!/usr/bin/env python3
"""
Script para crear números de serie de prueba con formato actualizado
y distribución por turnos para testing de funcionalidades mejoradas
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_system.settings')
django.setup()

from django.contrib.auth.models import User
from serials.models import SerialNumber, AuthorizedPart
from operations.models import Operation, ProcessRecord
from defects.models import Defect


def create_test_serial_numbers():
    """Crear números de serie de prueba con formato actualizado"""
    
    authorized_part, created = AuthorizedPart.objects.get_or_create(
        part_number='TEST-PCB-001',
        defaults={
            'sku': 'SKU-TEST-PCB-001-V1',
            'description': 'Tarjeta PCB de prueba para testing del sistema',
            'revision': 'Rev-A',
            'is_active': True
        }
    )
    
    if created:
        print(f"✓ Creada parte autorizada: {authorized_part.part_number} (SKU: {authorized_part.sku})")
    else:
        # Update existing part with SKU if missing
        if not hasattr(authorized_part, 'sku') or not authorized_part.sku:
            authorized_part.sku = 'SKU-TEST-PCB-001-V1'
            authorized_part.save()
            print(f"✓ SKU actualizado para parte: {authorized_part.part_number}")
        print(f"✓ Usando parte autorizada existente: {authorized_part.part_number} (SKU: {authorized_part.sku})")
    
    # Obtener usuario para crear los seriales
    try:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        if not user:
            print("❌ No hay usuarios en el sistema. Crea un usuario primero.")
            return
    except:
        print("❌ Error al obtener usuario")
        return
    
    serial_numbers_data = [
        {'serial_number': 'KA001-001M', 'order_number': 'ORD-2025-001'},
        {'serial_number': 'KA001-002M', 'order_number': 'ORD-2025-001'},
        {'serial_number': 'KA001-003M', 'order_number': 'ORD-2025-002'},
        {'serial_number': 'KA002-001M', 'order_number': 'ORD-2025-002'},
        {'serial_number': 'KA002-002M', 'order_number': 'ORD-2025-003'},
        {'serial_number': 'KA003-001M', 'order_number': 'ORD-2025-003'},
        {'serial_number': 'KA003-002M', 'order_number': 'ORD-2025-004'},
        {'serial_number': 'KA003-003M', 'order_number': 'ORD-2025-004'},
    ]
    
    serial_numbers = []
    now = timezone.now()
    
    for i, serial_data in enumerate(serial_numbers_data):
        serial_number = serial_data['serial_number']
        
        # Verificar si ya existe
        if SerialNumber.objects.filter(serial_number=serial_number).exists():
            print(f"⚠️  El número de serie {serial_number} ya existe")
            existing_serial = SerialNumber.objects.get(serial_number=serial_number)
            serial_numbers.append(existing_serial)
            continue
        
        # Distribute creation times across both shifts
        if i % 2 == 0:
            # First shift: 6:00 AM - 3:30 PM
            creation_time = now.replace(hour=8 + (i % 6), minute=30, second=0, microsecond=0)
        else:
            # Second shift: 3:30 PM - 12:00 AM
            creation_time = now.replace(hour=16 + (i % 6), minute=15, second=0, microsecond=0)
        
        # Crear el número de serie
        serial = SerialNumber.objects.create(
            serial_number=serial_number,
            authorized_part=authorized_part,
            order_number=serial_data['order_number'],
            created_by=user,
            status='CREATED'
        )
        
        # Update creation time to simulate shift distribution
        serial.created_at = creation_time
        serial.save()
        
        serial_numbers.append(serial)
        shift_name = "Primer Turno" if i % 2 == 0 else "Segundo Turno"
        print(f"✓ Creado número de serie: {serial.serial_number} ({shift_name})")
    
    # Verificar que se crearon los ProcessRecord automáticamente
    print("\n--- Verificando ProcessRecord creados ---")
    for serial in serial_numbers:
        process_records = ProcessRecord.objects.filter(serial_number=serial)
        print(f"Serial {serial.serial_number}: {process_records.count()} ProcessRecord creados")
        
        # Mostrar detalles de los primeros 3
        for record in process_records[:3]:
            print(f"  - {record.operation.name}: {record.status}")
    
    create_shift_distributed_defects(serial_numbers, user)
    
    # Mostrar resumen de operaciones disponibles
    print("\n--- Resumen de operaciones disponibles ---")
    operations = Operation.objects.filter(is_active=True).order_by('sequence_number')
    
    for operation in operations:
        free_count = ProcessRecord.objects.filter(
            operation=operation,
            status='PENDING',
            assigned_operator__isnull=True
        ).count()
        print(f"{operation.name}: {free_count} operaciones libres")
    
    print("\n--- Resumen por turnos ---")
    today = timezone.now().date()
    today_serials = SerialNumber.objects.filter(created_at__date=today)
    
    shift_1_count = 0
    shift_2_count = 0
    
    for serial in today_serials:
        hour = serial.created_at.hour
        if 6 <= hour < 15.5:  # 6:00 AM to 3:30 PM
            shift_1_count += 1
        elif 15.5 <= hour < 24:  # 3:30 PM to 12:00 AM
            shift_2_count += 1
    
    print(f"Números de serie creados hoy:")
    print(f"  • Primer Turno (6:00 AM - 3:30 PM): {shift_1_count}")
    print(f"  • Segundo Turno (3:30 PM - 12:00 AM): {shift_2_count}")
    
    print(f"\n✅ Proceso completado. Creados {len(serial_numbers)} números de serie.")
    print("Ahora puedes:")
    print("  • Buscar números de serie por SKU, parte o número de serie")
    print("  • Ver análisis de defectos por turno en el dashboard")
    print("  • Exportar CSV con columnas PN, SKU, SERIAL")
    print("  • Usar los botones 'Asignarme' en el resumen de operaciones")


def create_shift_distributed_defects(serial_numbers, user):
    """Create defects distributed across shifts for testing"""
    print("\n--- Creando defectos distribuidos por turnos ---")
    
    if len(serial_numbers) < 3:
        print("⚠️  No hay suficientes números de serie para crear defectos")
        return
    
    now = timezone.now()
    
    # Get first operation for defects
    first_operation = Operation.objects.filter(is_active=True).first()
    if not first_operation:
        print("⚠️  No hay operaciones disponibles para crear defectos")
        return
    
    # Defect in first shift (9:00 AM)
    first_shift_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    defect1, created = Defect.objects.get_or_create(
        serial_number=serial_numbers[0],
        operation=first_operation,
        defect_type='VISUAL',
        defaults={
            'description': 'Defecto de prueba - Primer Turno',
            'status': 'OPEN',
            'reported_by': user,
            'created_at': first_shift_time,
        }
    )
    
    if created:
        print(f"✓ Defecto primer turno creado: {defect1.serial_number.serial_number}")
    
    # Defect in second shift (5:00 PM)
    second_shift_time = now.replace(hour=17, minute=0, second=0, microsecond=0)
    defect2, created = Defect.objects.get_or_create(
        serial_number=serial_numbers[1],
        operation=first_operation,
        defect_type='FUNCTIONAL',
        defaults={
            'description': 'Defecto de prueba - Segundo Turno',
            'status': 'OPEN',
            'reported_by': user,
            'created_at': second_shift_time,
        }
    )
    
    if created:
        print(f"✓ Defecto segundo turno creado: {defect2.serial_number.serial_number}")


if __name__ == '__main__':
    create_test_serial_numbers()
