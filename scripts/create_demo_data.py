#!/usr/bin/env python3
"""
Script completo para generar todos los datos necesarios para probar
el sistema de asignación de operadores en el sistema de manufactura.
Incluye mejoras para campo SKU y análisis por turnos.

Ejecutar desde el directorio raíz del proyecto:
python scripts/create_demo_data.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_system.settings')
django.setup()

from django.contrib.auth.models import User
from operators.models import UserProfile
from serials.models import AuthorizedPart, SerialNumber
from operations.models import Operation, ProcessRecord
from defects.models import Defect


def create_users():
    """Crear usuarios con diferentes roles"""
    print("🔧 Creando usuarios...")
    
    users_data = [
        {
            'username': 'admin',
            'password': 'admin123',
            'first_name': 'Administrador',
            'last_name': 'Sistema',
            'email': 'admin@empresa.com',
            'is_staff': True,
            'is_superuser': True,
            'profile': {
                'employee_id': 'ADM001',
                'role': 'ADMIN',
                'department': 'Administración',
                'phone': '555-0001',
                'can_approve_operations': True,
                'can_generate_serials': True,
                'can_view_statistics': True,
                'can_manage_users': True,
            }
        },
        {
            'username': 'supervisor1',
            'password': 'super123',
            'first_name': 'Carlos',
            'last_name': 'Supervisor',
            'email': 'supervisor@empresa.com',
            'profile': {
                'employee_id': 'SUP001',
                'role': 'SUPERVISOR',
                'department': 'Producción',
                'phone': '555-0002',
                'can_approve_operations': True,
                'can_generate_serials': True,
                'can_view_statistics': True,
            }
        },
        {
            'username': 'operador1',
            'password': 'oper123',
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'email': 'juan.perez@empresa.com',
            'profile': {
                'employee_id': 'OP001',
                'role': 'OPERATOR',
                'department': 'Producción',
                'phone': '555-0101',
            }
        },
        {
            'username': 'operador2',
            'password': 'oper123',
            'first_name': 'María',
            'last_name': 'García',
            'email': 'maria.garcia@empresa.com',
            'profile': {
                'employee_id': 'OP002',
                'role': 'OPERATOR',
                'department': 'Producción',
                'phone': '555-0102',
            }
        },
        {
            'username': 'operador3',
            'password': 'oper123',
            'first_name': 'Pedro',
            'last_name': 'López',
            'email': 'pedro.lopez@empresa.com',
            'profile': {
                'employee_id': 'OP003',
                'role': 'OPERATOR',
                'department': 'Producción',
                'phone': '555-0103',
            }
        },
        {
            'username': 'calidad1',
            'password': 'qual123',
            'first_name': 'Ana',
            'last_name': 'Calidad',
            'email': 'ana.calidad@empresa.com',
            'profile': {
                'employee_id': 'QC001',
                'role': 'QUALITY',
                'department': 'Control de Calidad',
                'phone': '555-0201',
                'can_view_statistics': True,
            }
        },
        {
            'username': 'reparador1',
            'password': 'repa123',
            'first_name': 'Luis',
            'last_name': 'Reparador',
            'email': 'luis.reparador@empresa.com',
            'profile': {
                'employee_id': 'REP001',
                'role': 'REPAIRER',
                'department': 'Reparaciones',
                'phone': '555-0301',
            }
        }
    ]
    
    created_users = {}
    
    for user_data in users_data:
        # Crear o actualizar usuario
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'email': user_data['email'],
                'is_staff': user_data.get('is_staff', False),
                'is_superuser': user_data.get('is_superuser', False),
            }
        )
        
        if created:
            user.set_password(user_data['password'])
            user.save()
            print(f"  ✅ Usuario creado: {user.username}")
        else:
            print(f"  ℹ️  Usuario existente: {user.username}")
        
        # Crear o actualizar perfil
        profile_data = user_data['profile']
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults=profile_data
        )
        
        if not profile_created:
            # Actualizar perfil existente
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save()
        
        created_users[user_data['username']] = user
    
    return created_users


def create_authorized_parts():
    """Crear componentes autorizados con campos SKU"""
    print("📦 Creando componentes autorizados con SKUs...")
    
    parts_data = [
        {
            'part_number': 'PCB-MAIN-001',
            'sku': 'SKU-PCB-MAIN-001-V1',
            'description': 'Tarjeta Principal de Control',
            'revision': 'Rev-C'
        },
        {
            'part_number': 'PCB-PWR-002',
            'sku': 'SKU-PCB-PWR-002-V1',
            'description': 'Tarjeta de Alimentación',
            'revision': 'Rev-B'
        },
        {
            'part_number': 'CASE-ALU-003',
            'sku': 'SKU-CASE-ALU-003-V1',
            'description': 'Carcasa de Aluminio',
            'revision': 'Rev-A'
        },
        {
            'part_number': 'CONN-USB-004',
            'sku': 'SKU-CONN-USB-004-V1',
            'description': 'Conector USB Tipo-C',
            'revision': 'Rev-A'
        },
        {
            'part_number': 'LED-IND-005',
            'sku': 'SKU-LED-IND-005-V1',
            'description': 'LED Indicador Multicolor',
            'revision': 'Rev-A'
        }
    ]
    
    created_parts = {}
    
    for part_data in parts_data:
        part, created = AuthorizedPart.objects.get_or_create(
            part_number=part_data['part_number'],
            defaults={
                'sku': part_data['sku'],
                'description': part_data['description'],
                'revision': part_data['revision'],
                'is_active': True
            }
        )
        
        if not created and not hasattr(part, 'sku') or not part.sku:
            part.sku = part_data['sku']
            part.save()
            print(f"  🔄 SKU actualizado para: {part.part_number}")
        
        if created:
            print(f"  ✅ Componente creado: {part.part_number} (SKU: {part.sku})")
        else:
            print(f"  ℹ️  Componente existente: {part.part_number} (SKU: {part.sku})")
        
        created_parts[part_data['part_number']] = part
    
    return created_parts


def create_operations():
    """Crear operaciones de manufactura"""
    print("⚙️  Creando operaciones de manufactura...")
    
    operations_data = [
        {
            'name': 'Preparación de Materiales',
            'description': 'Preparación y verificación de todos los materiales necesarios',
            'sequence_number': 1,
            'estimated_time_minutes': 15,
        },
        {
            'name': 'Ensamble Inicial',
            'description': 'Ensamble inicial de componentes principales',
            'sequence_number': 2,
            'estimated_time_minutes': 30,
        },
        {
            'name': 'Soldadura',
            'description': 'Proceso de soldadura de componentes electrónicos',
            'sequence_number': 3,
            'estimated_time_minutes': 45,
        },
        {
            'name': 'Inspección Visual',
            'description': 'Inspección visual de calidad y acabados',
            'sequence_number': 4,
            'estimated_time_minutes': 20,
        },
        {
            'name': 'Pruebas Eléctricas',
            'description': 'Pruebas eléctricas y funcionales completas',
            'sequence_number': 5,
            'estimated_time_minutes': 25,
        },
        {
            'name': 'Calibración',
            'description': 'Calibración final de parámetros del dispositivo',
            'sequence_number': 6,
            'estimated_time_minutes': 20,
        },
        {
            'name': 'Empaque Final',
            'description': 'Empaque final y etiquetado del producto',
            'sequence_number': 7,
            'estimated_time_minutes': 10,
        }
    ]
    
    created_operations = {}
    
    for op_data in operations_data:
        operation, created = Operation.objects.get_or_create(
            sequence_number=op_data['sequence_number'],
            defaults={
                'name': op_data['name'],
                'description': op_data['description'],
                'estimated_time_minutes': op_data['estimated_time_minutes'],
                'requires_approval': True,
                'is_active': True
            }
        )
        
        if created:
            print(f"  ✅ Operación creada: {operation.sequence_number}. {operation.name}")
        else:
            print(f"  ℹ️  Operación existente: {operation.sequence_number}. {operation.name}")
        
        created_operations[op_data['sequence_number']] = operation
    
    return created_operations


def create_serial_numbers(users, parts):
    """Crear números de serie que generarán ProcessRecord automáticamente"""
    print("🏷️  Creando números de serie...")
    
    # Obtener el usuario admin para crear los seriales
    admin_user = users['admin']
    
    # Usar el primer componente disponible
    main_part = list(parts.values())[0]
    
    serial_numbers_data = [
        {
            'serial_number': 'KA001-001M',
            'order_number': 'ORD-2025-001',
        },
        {
            'serial_number': 'KA001-002M',
            'order_number': 'ORD-2025-001',
        },
        {
            'serial_number': 'KA001-003M',
            'order_number': 'ORD-2025-002',
        },
        {
            'serial_number': 'KA002-001M',
            'order_number': 'ORD-2025-002',
        },
        {
            'serial_number': 'KA002-002M',
            'order_number': 'ORD-2025-003',
        },
        {
            'serial_number': 'KA002-003M',
            'order_number': 'ORD-2025-003',
        },
        {
            'serial_number': 'KA003-001M',
            'order_number': 'ORD-2025-004',
        },
        {
            'serial_number': 'KA003-002M',
            'order_number': 'ORD-2025-004',
        }
    ]
    
    created_serials = []
    
    for serial_data in serial_numbers_data:
        serial, created = SerialNumber.objects.get_or_create(
            serial_number=serial_data['serial_number'],
            defaults={
                'order_number': serial_data['order_number'],
                'authorized_part': main_part,
                'status': 'IN_PROCESS',
                'created_by': admin_user,
            }
        )
        
        if created:
            print(f"  ✅ Número de serie creado: {serial.serial_number}")
            created_serials.append(serial)
        else:
            print(f"  ℹ️  Número de serie existente: {serial.serial_number}")
            created_serials.append(serial)
    
    return created_serials


def assign_some_operators(users, serials):
    """Asignar algunos operadores a operaciones para mostrar el sistema funcionando"""
    print("👥 Asignando algunos operadores a operaciones...")
    
    # Obtener operadores
    operador1 = users['operador1']
    operador2 = users['operador2']
    
    # Asignar operador1 a la primera operación del primer serial
    if serials:
        first_serial = serials[0]
        first_process = ProcessRecord.objects.filter(
            serial_number=first_serial,
            operation__sequence_number=1
        ).first()
        
        if first_process and first_process.status == 'PENDING':
            first_process.assigned_operator = operador1
            first_process.status = 'IN_PROGRESS'
            first_process.assigned_at = timezone.now()
            first_process.save()
            print(f"  ✅ {operador1.get_full_name()} asignado a {first_process}")
        
        # Asignar operador2 a la segunda operación del segundo serial
        if len(serials) > 1:
            second_serial = serials[1]
            second_process = ProcessRecord.objects.filter(
                serial_number=second_serial,
                operation__sequence_number=2
            ).first()
            
            if second_process and second_process.status == 'PENDING':
                second_process.assigned_operator = operador2
                second_process.status = 'IN_PROGRESS'
                second_process.assigned_at = timezone.now()
                second_process.save()
                print(f"  ✅ {operador2.get_full_name()} asignado a {second_process}")


def create_sample_defects_by_shift(users, serials):
    """Crear defectos de ejemplo distribuidos en diferentes turnos"""
    print("🔍 Creando defectos de ejemplo por turnos...")
    
    if not serials:
        print("  ⚠️  No hay números de serie para crear defectos")
        return
    
    calidad_user = users['calidad1']
    reparador_user = users['reparador1']
    
    now = timezone.now()
    
    # Defecto en primer turno (8:00 AM)
    first_shift_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    defect1, created = Defect.objects.get_or_create(
        serial_number=serials[0],
        operation_id=3,  # Soldadura
        defect_type='VISUAL',
        defaults={
            'description': 'Soldadura fría detectada en conector principal - Primer Turno',
            'status': 'OPEN',
            'reported_by': calidad_user,
            'created_at': first_shift_time,
        }
    )
    
    if created:
        print(f"  ✅ Defecto primer turno creado: {defect1}")
    
    # Defecto en segundo turno (4:00 PM)
    if len(serials) > 1:
        second_shift_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
        defect2, created = Defect.objects.get_or_create(
            serial_number=serials[1],
            operation_id=4,  # Inspección Visual
            defect_type='DIMENSIONAL',
            defaults={
                'description': 'Dimensiones fuera de tolerancia en carcasa - Segundo Turno',
                'status': 'IN_REPAIR',
                'reported_by': calidad_user,
                'assigned_repairer': reparador_user,
                'assigned_at': second_shift_time,
                'created_at': second_shift_time,
            }
        )
        
        if created:
            print(f"  ✅ Defecto segundo turno creado: {defect2}")
    
    # Defecto adicional en segundo turno (6:00 PM)
    if len(serials) > 2:
        late_second_shift_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
        defect3, created = Defect.objects.get_or_create(
            serial_number=serials[2],
            operation_id=5,  # Pruebas Eléctricas
            defect_type='FUNCTIONAL',
            defaults={
                'description': 'Falla en prueba de conectividad - Segundo Turno',
                'status': 'OPEN',
                'reported_by': calidad_user,
                'created_at': late_second_shift_time,
            }
        )
        
        if created:
            print(f"  ✅ Defecto segundo turno (tarde) creado: {defect3}")


def print_summary(users, parts, operations, serials):
    """Imprimir resumen de datos creados"""
    print("\n" + "="*60)
    print("📊 RESUMEN DE DATOS CREADOS")
    print("="*60)
    
    print(f"👥 Usuarios creados: {len(users)}")
    for username, user in users.items():
        role = user.userprofile.role if hasattr(user, 'userprofile') else 'N/A'
        print(f"   • {username} ({user.get_full_name()}) - {role}")
    
    print(f"\n📦 Componentes autorizados: {len(parts)}")
    for part in parts.values():
        print(f"   • {part.part_number} (SKU: {part.sku}) - {part.description}")
    
    print(f"\n⚙️  Operaciones: {len(operations)}")
    for op in operations.values():
        print(f"   • {op.sequence_number}. {op.name}")
    
    print(f"\n🏷️  Números de serie: {len(serials)}")
    for serial in serials:
        print(f"   • {serial.serial_number} ({serial.order_number}) - SKU: {serial.authorized_part.sku}")
    
    # Contar ProcessRecord pendientes
    pending_records = ProcessRecord.objects.filter(status='PENDING').count()
    assigned_records = ProcessRecord.objects.filter(status='IN_PROGRESS').count()
    
    print(f"\n📋 Registros de proceso:")
    print(f"   • Pendientes: {pending_records}")
    print(f"   • Asignados: {assigned_records}")
    
    total_defects = Defect.objects.count()
    today = timezone.now().date()
    today_defects = Defect.objects.filter(created_at__date=today)
    
    shift_1_count = 0
    shift_2_count = 0
    
    for defect in today_defects:
        hour = defect.created_at.hour
        if 6 <= hour < 15.5:  # 6:00 AM to 3:30 PM
            shift_1_count += 1
        elif 15.5 <= hour < 24:  # 3:30 PM to 12:00 AM
            shift_2_count += 1
    
    print(f"\n🔍 Defectos: {total_defects}")
    print(f"   • Primer Turno (6:00 AM - 3:30 PM): {shift_1_count}")
    print(f"   • Segundo Turno (3:30 PM - 12:00 AM): {shift_2_count}")
    
    print("\n" + "="*60)
    print("✅ SISTEMA LISTO PARA USAR")
    print("="*60)
    print("🌐 Accede a: http://127.0.0.1:8000/analytics/dashboard/")
    print("👤 Usuarios de prueba:")
    print("   • admin / admin123 (Administrador)")
    print("   • supervisor1 / super123 (Supervisor)")
    print("   • operador1 / oper123 (Operador)")
    print("   • operador2 / oper123 (Operador)")
    print("   • operador3 / oper123 (Operador)")
    print("   • calidad1 / qual123 (Control de Calidad)")
    print("   • reparador1 / repa123 (Reparador)")
    print("\n🔍 Funcionalidades implementadas:")
    print("   • Campo SKU en componentes y CSV")
    print("   • Búsqueda de números de serie por SKU, parte, orden")
    print("   • Dashboard con defectos por turno")
    print("   • Análisis de primer turno (6:00 AM - 3:30 PM)")
    print("   • Análisis de segundo turno (3:30 PM - 12:00 AM)")


def main():
    """Función principal"""
    print("🚀 INICIANDO CONFIGURACIÓN COMPLETA DEL SISTEMA CON MEJORAS")
    print("="*60)
    
    try:
        # Crear todos los datos necesarios
        users = create_users()
        parts = create_authorized_parts()
        operations = create_operations()
        serials = create_serial_numbers(users, parts)
        
        # Asignar algunos operadores para demostrar funcionalidad
        assign_some_operators(users, serials)
        
        # Crear defectos de ejemplo distribuidos por turnos
        create_sample_defects_by_shift(users, serials)
        
        # Mostrar resumen
        print_summary(users, parts, operations, serials)
        
    except Exception as e:
        print(f"❌ Error durante la configuración: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 ¡Configuración completada exitosamente!")
    else:
        print("\n💥 Error en la configuración")
        sys.exit(1)
