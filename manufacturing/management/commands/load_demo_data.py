from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from operators.models import UserProfile  # Updated import
from serials.models import AuthorizedPart, SerialNumber  # Updated import
from operations.models import Operation, ProcessRecord  # Updated import
from django.db import transaction
import random
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Carga datos de demostración para el sistema de manufactura'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando carga de datos de demostración...'))
        
        with transaction.atomic():
            # Crear usuarios de demostración
            self.create_demo_users()
            
            # Crear partes autorizadas
            self.create_authorized_parts()
            
            # Crear operaciones de manufactura
            self.create_operations()
            
            # Crear números de serie de demostración
            self.create_demo_serials()
            
        self.stdout.write(self.style.SUCCESS('¡Datos de demostración cargados exitosamente!'))
        self.stdout.write('Usuarios creados:')
        self.stdout.write('- admin/admin123 (Administrador)')
        self.stdout.write('- operador1/pass123 (Operador)')
        self.stdout.write('- operador2/pass123 (Operador)')
        self.stdout.write('- supervisor/pass123 (Supervisor)')

    def create_demo_users(self):
        # Crear superusuario admin si no existe
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@empresa.com',
                password='admin123',
                first_name='Administrador',
                last_name='Sistema'
            )
            UserProfile.objects.create(
                user=admin,
                role='ADMIN',  # Fixed role value to match model choices
                employee_id='ADM001',
                can_approve_operations=True,
                can_generate_serials=True,
                can_view_statistics=True,
                can_manage_users=True
            )
            self.stdout.write(f'Usuario admin creado')

        # Crear usuarios operadores
        operators = [
            ('operador1', 'Juan', 'Pérez', 'OP001', 'OPERATOR'),
            ('operador2', 'María', 'González', 'OP002', 'OPERATOR'),
            ('supervisor', 'Carlos', 'Rodríguez', 'SUP001', 'SUPERVISOR')
        ]
        
        for username, first_name, last_name, emp_id, role in operators:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@empresa.com',
                    password='pass123',
                    first_name=first_name,
                    last_name=last_name
                )
                UserProfile.objects.create(
                    user=user,
                    role=role,
                    employee_id=emp_id,
                    can_approve_operations=(role == 'SUPERVISOR'),
                    can_generate_serials=True,
                    can_view_statistics=(role in ['SUPERVISOR', 'ADMIN'])
                )
                self.stdout.write(f'Usuario {username} creado')

    def create_authorized_parts(self):
        parts_data = [
            ('PCB-001', 'Placa Base Principal', 'Rev A'),
            ('PCB-002', 'Placa de Control', 'Rev B'),
            ('PCB-003', 'Placa de Potencia', 'Rev A'),
            ('ASM-001', 'Ensamble Motor', 'Rev C'),
            ('ASM-002', 'Ensamble Sensor', 'Rev A'),
            ('CMP-001', 'Componente Crítico', 'Rev B'),
            ('MOD-001', 'Módulo Principal', 'Rev A'),
            ('MOD-002', 'Módulo Secundario', 'Rev A'),
        ]
        
        for part_number, description, revision in parts_data:
            part, created = AuthorizedPart.objects.get_or_create(
                part_number=part_number,
                defaults={
                    'description': description,
                    'revision': revision,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'Parte autorizada creada: {part_number}')

    def create_operations(self):
        operations_data = [
            ('Preparación de Materiales', 1, 30),
            ('Ensamble Inicial', 2, 45),
            ('Soldadura', 3, 60),
            ('Inspección Visual', 4, 20),
            ('Pruebas Eléctricas', 5, 40),
            ('Calibración', 6, 35),
            ('Empaque Final', 7, 25),
        ]
        
        for name, sequence, time_minutes in operations_data:
            operation, created = Operation.objects.get_or_create(
                sequence_number=sequence,
                defaults={
                    'name': name,
                    'description': f'Descripción detallada de {name}',
                    'estimated_time_minutes': time_minutes,
                    'requires_approval': True,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'Operación creada: {sequence} - {name}')

    def create_demo_serials(self):
        # Obtener datos necesarios
        parts = list(AuthorizedPart.objects.all())
        operations = list(Operation.objects.all().order_by('sequence_number'))
        users = list(User.objects.filter(userprofile__role__in=['OPERATOR', 'SUPERVISOR']))
        
        if not parts or not operations or not users:
            self.stdout.write(self.style.WARNING('No hay suficientes datos para crear números de serie'))
            return
        
        # Crear números de serie de demostración
        for i in range(1, 21):  # Crear 20 números de serie
            part = random.choice(parts)
            order_number = f'ORD-2024-{i:04d}'
            
            # Generar número de serie con formato KM###W###R
            serial_num = f'KM{i:03d}W{random.randint(1, 999):03d}R'
            
            serial = SerialNumber.objects.create(
                serial_number=serial_num,
                authorized_part=part,
                order_number=order_number,
                created_by=random.choice(users)
            )
            
            # Simular progreso en operaciones
            completed_ops = random.randint(0, len(operations))
            
            for j, operation in enumerate(operations[:completed_ops]):
                ProcessRecord.objects.create(
                    serial_number=serial,
                    operation=operation,
                    processed_by=random.choice(users),
                    completed_at=datetime.now() - timedelta(
                        days=random.randint(0, 30),
                        hours=random.randint(0, 23)
                    ),
                    status='APPROVED',  # Fixed status value to match model choices
                    notes=f'Operación completada satisfactoriamente',
                    quality_check_passed=True
                )
            
            self.stdout.write(f'Número de serie creado: {serial.serial_number}')
