from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from operations.models import Operation  # Updated import path
from serials.models import AuthorizedPart  # Updated import path
from operators.models import UserProfile  # Added UserProfile import


class Command(BaseCommand):
    help = 'Setup initial data for manufacturing system'

    def handle(self, *args, **options):
        # Create default operations
        operations_data = [
            {
                'sequence_number': 1,
                'name': 'Preparación de Materiales',
                'description': 'Preparar y verificar todos los materiales necesarios',
                'estimated_time_minutes': 30,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 2,
                'name': 'Ensamble Inicial',
                'description': 'Realizar el ensamble inicial del componente',
                'estimated_time_minutes': 45,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 3,
                'name': 'Soldadura',
                'description': 'Proceso de soldadura según especificaciones',
                'estimated_time_minutes': 60,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 4,
                'name': 'Control de Calidad Intermedio',
                'description': 'Verificación de calidad en proceso intermedio',
                'estimated_time_minutes': 20,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 5,
                'name': 'Acabado Final',
                'description': 'Aplicar acabado final al componente',
                'estimated_time_minutes': 40,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 6,
                'name': 'Pruebas Funcionales',
                'description': 'Realizar pruebas funcionales completas',
                'estimated_time_minutes': 35,
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'sequence_number': 7,
                'name': 'Empaque y Etiquetado',
                'description': 'Empaque final y etiquetado del producto',
                'estimated_time_minutes': 15,
                'is_active': True  # Explicitly set is_active to True
            }
        ]

        for op_data in operations_data:
            operation, created = Operation.objects.get_or_create(
                sequence_number=op_data['sequence_number'],
                defaults=op_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created operation: {operation.name}')
                )

        # Create sample authorized parts
        parts_data = [
            {
                'part_number': 'PCB-001',
                'description': 'Placa de Circuito Impreso Principal',
                'revision': 'A',
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'part_number': 'CASE-002',
                'description': 'Carcasa de Aluminio Estándar',
                'revision': 'B',
                'is_active': True  # Explicitly set is_active to True
            },
            {
                'part_number': 'CONN-003',
                'description': 'Conector USB Tipo C',
                'revision': 'A',
                'is_active': True  # Explicitly set is_active to True
            }
        ]

        for part_data in parts_data:
            part, created = AuthorizedPart.objects.get_or_create(
                part_number=part_data['part_number'],
                defaults=part_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created authorized part: {part.part_number}')
                )

        # Create admin user if it doesn't exist
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@manufacturing.com',
                password='admin123',
                first_name='Administrador',
                last_name='Sistema'
            )
            profile, created = UserProfile.objects.get_or_create(
                user=admin_user,
                defaults={
                    'employee_id': 'ADM001',
                    'role': 'ADMIN',
                    'can_approve_operations': True,
                    'can_view_statistics': True,
                    'can_manage_users': True,
                    'can_generate_serials': True
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS('Created admin user (username: admin, password: admin123)')
            )

        self.stdout.write(
            self.style.SUCCESS('Initial data setup completed successfully!')
        )
